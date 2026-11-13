"""Show the rental tables in the Django admin (/admin/)."""
from django.contrib import admin

from .models import Amenity, Lease, Property

admin.site.register(Amenity)


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("title", "city", "rent_amount", "owner", "is_available")
    list_filter = ("city", "is_available")


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
    list_display = ("property", "tenant", "start_date", "end_date", "is_active")
