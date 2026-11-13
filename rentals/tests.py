"""
One simple test that walks through the whole API like a real user would.
Run it with:   docker compose exec web python manage.py test
"""
import re
from datetime import date, timedelta

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from core.celery import app as celery_app
from rentals.models import Amenity

# Use fake email + in-memory cache while testing (no real SMTP / Redis needed)
TEST_SETTINGS = dict(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)


@override_settings(**TEST_SETTINGS)
class FullFlowTest(TestCase):
    def setUp(self):
        celery_app.conf.task_always_eager = True  # run tasks immediately, no worker needed
        cache.clear()
        self.client = APIClient()

    def register_and_login(self, email, role):
        self.client.post("/api/auth/register/", {
            "email": email, "full_name": email.split("@")[0], "password": "StrongPass#123", "role": role,
        }, format="json")
        res = self.client.post("/api/auth/login/", {"email": email, "password": "StrongPass#123"}, format="json")
        self.assertEqual(res.status_code, 200)
        return res.data["access"]

    def test_full_flow(self):
        # ---- register + login (welcome email goes out)
        owner_token = self.register_and_login("owner@example.com", "owner")
        self.assertEqual(len(mail.outbox), 1)  # the welcome email was sent
        tenant_token = self.register_and_login("tenant@example.com", "tenant")

        # ---- me + nested profile update
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_token}")
        res = self.client.patch("/api/auth/me/", {"profile": {"phone": "0123", "city": "Dhaka"}}, format="json")
        self.assertEqual(res.data["profile"]["city"], "Dhaka")

        # ---- amenities (admin adds them directly here)
        wifi = Amenity.objects.create(name="WiFi")
        parking = Amenity.objects.create(name="Parking")

        # ---- tenant cannot create a property, owner can
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tenant_token}")
        res = self.client.post("/api/properties/", {"title": "x"}, format="json")
        self.assertEqual(res.status_code, 403)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_token}")
        res = self.client.post("/api/properties/", {
            "title": "Sunny flat", "address": "12 Lake Road", "city": "Dhaka",
            "rent_amount": "500.00", "bedrooms": 2, "amenity_ids": [wifi.id, parking.id],
        }, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(res.data["amenities"]), 2)           # nested amenities
        self.assertEqual(res.data["owner"]["profile"]["city"], "Dhaka")  # nested owner -> profile
        property_id = res.data["id"]

        # ---- list is cached: first MISS, then HIT, and a change clears it
        res = self.client.get("/api/properties/?city=dhaka")
        self.assertEqual(res["X-Cache"], "MISS")
        self.assertEqual(len(res.data), 1)
        res = self.client.get("/api/properties/?city=dhaka")
        self.assertEqual(res["X-Cache"], "HIT")
        self.assertEqual(self.client.get("/api/properties/?min_rent=abc").status_code, 400)

        # ---- owner creates a lease for the tenant
        tenant = User.objects.get(email="tenant@example.com")
        mail.outbox.clear()
        res = self.client.post("/api/leases/", {
            "property_id": property_id, "tenant_id": tenant.id,
            "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["monthly_rent"], "500.00")       # defaulted from the property
        self.assertEqual(res.data["tenant"]["email"], "tenant@example.com")
        self.assertEqual(len(mail.outbox), 1)                      # lease email sent
        lease_id = res.data["id"]

        res = self.client.get("/api/properties/")
        self.assertEqual(res["X-Cache"], "MISS")
        self.assertEqual(len(res.data), 0)                         # rented -> not in the list anymore

        # ---- tenant sees their lease, then owner ends it
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tenant_token}")
        self.assertEqual(len(self.client.get("/api/leases/").data), 1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_token}")
        self.assertEqual(self.client.post(f"/api/leases/{lease_id}/end/").status_code, 200)
        self.assertEqual(len(self.client.get("/api/properties/").data), 1)

    def test_forgot_and_reset_password(self):
        self.register_and_login("sam@example.com", "tenant")
        mail.outbox.clear()
        self.client.credentials()  # no token

        res = self.client.post("/api/auth/forgot-password/", {"email": "sam@example.com"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

        body = mail.outbox[0].body
        uid = re.search(r"uid: (\S+)", body).group(1)
        token = re.search(r"token: (\S+)", body).group(1)

        res = self.client.post("/api/auth/reset-password/", {
            "uid": uid, "token": token, "new_password": "BrandNew#Pass456"}, format="json")
        self.assertEqual(res.status_code, 200)

        # the same link cannot be used twice
        res = self.client.post("/api/auth/reset-password/", {
            "uid": uid, "token": token, "new_password": "AnotherOne#789"}, format="json")
        self.assertEqual(res.status_code, 400)

        res = self.client.post("/api/auth/login/", {"email": "sam@example.com", "password": "BrandNew#Pass456"}, format="json")
        self.assertEqual(res.status_code, 200)

        # an unknown email gets the same answer (no information leak) and sends nothing
        mail.outbox.clear()
        res = self.client.post("/api/auth/forgot-password/", {"email": "nobody@example.com"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
