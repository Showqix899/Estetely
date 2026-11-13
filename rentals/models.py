"""
Database tables for renting.

Table 3: Amenity   -> something a property offers (WiFi, Parking, ...)
Table 4: Property  -> a house / flat that an owner rents out
                      * many properties belong to one owner   (foreign key)
                      * a property has many amenities and an amenity belongs
                        to many properties                    (many-to-many)
Table 5: Lease     -> a rental agreement: one tenant rents one property for a period
"""
from django.conf import settings
from django.db import models


class Amenity(models.Model):
    """A feature a property can have, e.g. 'WiFi' or 'Parking'."""

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "amenities"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Property(models.Model):
    """A property (house, flat, room) that an owner puts up for rent."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="properties")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2)  # rent per month
    bedrooms = models.PositiveSmallIntegerField(default=1)
    bathrooms = models.PositiveSmallIntegerField(default=1)
    is_available = models.BooleanField(default=True)  # False while someone is renting it
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="properties")  # many-to-many
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "properties"
        ordering = ["-created_at"]  # newest first

    def __str__(self):
        return self.title


class Lease(models.Model):
    """A rental agreement between a tenant and a property."""

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="leases")
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leases")
    start_date = models.DateField()
    end_date = models.DateField()
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tenant.email} -> {self.property.title}"



class LeaseRequest(models.Model):
    """
    A tenant's request to rent a property.
    pending -> the owner approves  -> a Lease is created        (approved)
            -> the owner rejects                                  (rejected)
            -> the tenant withdraws                               (cancelled)
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="lease_requests")
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lease_requests")
    start_date = models.DateField()
    end_date = models.DateField()
    message = models.TextField(blank=True)  # a short note from the tenant to the owner
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    # filled in when the owner approves (one request <-> one lease)
    lease = models.OneToOneField(Lease, null=True, blank=True, on_delete=models.SET_NULL, related_name="request")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tenant.email} -> {self.property.title} ({self.status})"