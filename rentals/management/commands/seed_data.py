"""
Fills the database with sample data so you can try the API quickly.

Run it with:
    docker compose exec web python manage.py seed_data
Delete the sample users (and their properties/leases) and create them again:
    docker compose exec web python manage.py seed_data --reset

Every sample user has the password:  Password#123
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Profile, User
from rentals.cache_utils import bump_cache_version
from rentals.models import Amenity, Lease, Property

PASSWORD = "Password#123"

AMENITIES = ["WiFi", "Parking", "Air Conditioning", "Elevator", "Generator", "Security Guard", "Balcony", "Furnished"]

# (email, full name, role, phone, address, city)
USERS = [
    ("owner1@example.com", "Rahim Uddin", "owner", "01711000001", "House 5, Road 3, Agrabad", "Chittagong"),
    ("owner2@example.com", "Nasrin Akter", "owner", "01711000002", "Flat 8B, Dhanmondi", "Dhaka"),
    ("tenant1@example.com", "Karim Hossain", "tenant", "01811000001", "Panchlaish", "Chittagong"),
    ("tenant2@example.com", "Sadia Islam", "tenant", "01811000002", "Mirpur 10", "Dhaka"),
    ("tenant3@example.com", "Tanvir Ahmed", "tenant", "01811000003", "Uttara Sector 7", "Dhaka"),
]

# (owner email, title, address, city, rent, bedrooms, bathrooms, amenities)
PROPERTIES = [
    ("owner1@example.com", "Sea View Apartment", "Agrabad Commercial Area", "Chittagong", "25000", 3, 2, ["WiFi", "Parking", "Elevator", "Balcony"]),
    ("owner1@example.com", "Cozy Studio near CDA Avenue", "CDA Avenue, Panchlaish", "Chittagong", "12000", 1, 1, ["WiFi", "Furnished"]),
    ("owner1@example.com", "Family Flat in Khulshi", "Khulshi Residential Area", "Chittagong", "30000", 4, 3, ["Parking", "Generator", "Security Guard", "Air Conditioning"]),
    ("owner2@example.com", "Modern Flat in Dhanmondi", "Road 27, Dhanmondi", "Dhaka", "35000", 3, 2, ["WiFi", "Elevator", "Generator", "Air Conditioning"]),
    ("owner2@example.com", "Budget Room in Mirpur", "Section 10, Mirpur", "Dhaka", "8000", 1, 1, ["WiFi"]),
    ("owner2@example.com", "Luxury Penthouse Gulshan", "Gulshan Avenue", "Dhaka", "80000", 4, 4, ["WiFi", "Parking", "Elevator", "Security Guard", "Furnished", "Balcony"]),
]

# (tenant email, property title) -> these two properties get rented
LEASES = [
    ("tenant1@example.com", "Sea View Apartment"),
    ("tenant2@example.com", "Modern Flat in Dhanmondi"),
]


class Command(BaseCommand):
    help = "Create sample users, amenities, properties and leases."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="delete the sample users first")

    def handle(self, *args, **options):
        # --reset: deleting a user also deletes their properties, leases and profile
        if options["reset"]:
            User.objects.filter(email__in=[u[0] for u in USERS]).delete()
            self.stdout.write("Old sample data deleted.")

        # 1) amenities
        amenity_map = {name: Amenity.objects.get_or_create(name=name)[0] for name in AMENITIES}

        # 2) users + profiles (one-to-one)
        user_map = {}
        for email, full_name, role, phone, address, city in USERS:
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(email=email, password=PASSWORD, full_name=full_name, role=role)
            Profile.objects.update_or_create(user=user, defaults={"phone": phone, "address": address, "city": city})
            user_map[email] = user

        # 3) properties + amenities (many-to-many)
        property_map = {}
        for owner_email, title, address, city, rent, beds, baths, amenity_names in PROPERTIES:
            rental, _ = Property.objects.get_or_create(
                owner=user_map[owner_email],
                title=title,
                defaults={
                    "description": f"{title}: a comfortable place to live in {city}.",
                    "address": address,
                    "city": city,
                    "rent_amount": Decimal(rent),
                    "bedrooms": beds,
                    "bathrooms": baths,
                },
            )
            rental.amenities.set([amenity_map[name] for name in amenity_names])
            property_map[title] = rental

        # 4) leases (the rented property becomes unavailable)
        today = timezone.localdate()
        for tenant_email, title in LEASES:
            rental = property_map[title]
            if Lease.objects.filter(property=rental, is_active=True).exists():
                continue  # already rented
            Lease.objects.create(
                property=rental,
                tenant=user_map[tenant_email],
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=335),
                monthly_rent=rental.rent_amount,
            )
            rental.is_available = False
            rental.save()

        bump_cache_version()  # clear the old cached property list

        self.stdout.write(self.style.SUCCESS(
            f"Done: {User.objects.count()} users, {Amenity.objects.count()} amenities, "
            f"{Property.objects.count()} properties, {Lease.objects.count()} leases."
        ))
        self.stdout.write(f"Log in with any sample email (owner1@example.com, tenant1@example.com ...) and password: {PASSWORD}")