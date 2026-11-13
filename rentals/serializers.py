"""
Serializers for the rentals app (with nested serializers).

Reading : the JSON contains nested objects (owner, amenities, property, tenant).
Writing : we send simple ids instead (amenity_ids, property_id, tenant_id).
"""
from rest_framework import serializers

from accounts.models import User
from accounts.serializers import UserSerializer

from .models import Amenity, Lease, Property,LeaseRequest


class AmenitySerializer(serializers.ModelSerializer):
    """Shows an amenity (id + name)."""

    class Meta:
        model = Amenity
        fields = ["id", "name"]


class PropertySerializer(serializers.ModelSerializer):
    """
    A property with nested data:
      * owner     -> the full user (with their profile inside)
      * amenities -> a list of amenity objects
    To choose amenities when creating/updating, send  "amenity_ids": [1, 2]
    """

    owner = UserSerializer(read_only=True)                       # nested, read only
    amenities = AmenitySerializer(many=True, read_only=True)     # nested list, read only
    amenity_ids = serializers.PrimaryKeyRelatedField(            # used only when writing
        queryset=Amenity.objects.all(),
        many=True,
        write_only=True,
        required=False,
        source="amenities",
    )

    class Meta:
        model = Property
        fields = [
            "id", "title", "description", "address", "city",
            "rent_amount", "bedrooms", "bathrooms", "is_available",
            "owner", "amenities", "amenity_ids", "created_at",
        ]
        read_only_fields = ["id", "is_available", "created_at"]  # is_available is changed by leases


class PropertyShortSerializer(serializers.ModelSerializer):
    """A small version of a property, used inside a lease so the JSON stays short."""

    class Meta:
        model = Property
        fields = ["id", "title", "address", "city", "rent_amount"]


class LeaseSerializer(serializers.ModelSerializer):
    """
    A lease with nested data:
      * property -> short property info
      * tenant   -> the full user (with profile)
    To create a lease send  property_id, tenant_id, start_date, end_date
    (monthly_rent is optional: it defaults to the property's rent).
    """

    property = PropertyShortSerializer(read_only=True)  # nested, read only
    tenant = UserSerializer(read_only=True)             # nested, read only
    property_id = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.all(), write_only=True, source="property"
    )
    tenant_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role="tenant"), write_only=True, source="tenant"
    )

    class Meta:
        model = Lease
        fields = [
            "id", "property", "tenant", "property_id", "tenant_id",
            "start_date", "end_date", "monthly_rent", "is_active", "created_at",
        ]
        read_only_fields = ["id", "is_active", "created_at"]
        extra_kwargs = {"monthly_rent": {"required": False}}

    def validate_property_id(self, value):
        """The logged-in owner can only create leases for their OWN, available properties."""
        if value.owner != self.context["request"].user:
            raise serializers.ValidationError("You can only create leases for your own properties.")
        if not value.is_available:
            raise serializers.ValidationError("This property is not available right now.")
        return value

    def validate(self, data):
        """The end date must be after the start date."""
        if data["end_date"] <= data["start_date"]:
            raise serializers.ValidationError("end_date must be after start_date.")
        return data

    def create(self, validated_data):
        rental = validated_data["property"]
        # If no rent was sent, use the property's normal rent
        validated_data.setdefault("monthly_rent", rental.rent_amount)

        lease = super().create(validated_data)

        # The property is now rented, so it is no longer available
        rental.is_available = False
        rental.save()
        return lease


class LeaseRequestSerializer(serializers.ModelSerializer):
    """
    A tenant's request to rent a property.
    To create one send  property_id, start_date, end_date and (optional) message.
    status and lease are set by the system when the owner approves / rejects.
    """

    property = PropertyShortSerializer(read_only=True)  # nested, read only
    tenant = UserSerializer(read_only=True)             # nested, read only
    property_id = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.all(), write_only=True, source="property"
    )
    lease = serializers.PrimaryKeyRelatedField(read_only=True)  # id of the lease created on approval

    class Meta:
        model = LeaseRequest
        fields = [
            "id", "property", "tenant", "property_id",
            "start_date", "end_date", "message", "status", "lease", "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def validate_property_id(self, value):
        """The property must be free, and the tenant must not already have a pending request for it."""
        if not value.is_available:
            raise serializers.ValidationError("This property is not available right now.")
        tenant = self.context["request"].user
        if LeaseRequest.objects.filter(property=value, tenant=tenant, status="pending").exists():
            raise serializers.ValidationError("You already have a pending request for this property.")
        return value

    def validate(self, data):
        """The end date must be after the start date."""
        if data["end_date"] <= data["start_date"]:
            raise serializers.ValidationError("end_date must be after start_date.")
        return data