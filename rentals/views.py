"""
Views for the rentals app. Every view is an APIView class.
All endpoints need a logged-in user (see DEFAULT_PERMISSION_CLASSES in settings.py).
"""
import hashlib
from django.db import transaction

from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import ErrorSerializer

from .cache_utils import bump_cache_version, get_cache_version
from .models import Amenity, Lease, LeaseRequest, Property
from .permissions import IsOwnerRole, IsTenantRole
from .serializers import AmenitySerializer, LeaseRequestSerializer, LeaseSerializer, PropertySerializer
from .tasks import send_lease_email, send_request_status_email


class AmenityListCreateView(APIView):
    """
    GET  /api/amenities/  -> list all amenities
    POST /api/amenities/  -> add an amenity (admin only)
    """

    def get_permissions(self):
        # Only admins may add amenities; any logged-in user may read them
        if self.request.method == "POST":
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @extend_schema(tags=["Amenities"], responses=AmenitySerializer(many=True))
    def get(self, request):
        amenities = Amenity.objects.all()
        return Response(AmenitySerializer(amenities, many=True).data)

    @extend_schema(tags=["Amenities"], request=AmenitySerializer, responses={201: AmenitySerializer})
    def post(self, request):
        serializer = AmenitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PropertyListCreateView(APIView):
    """
    GET  /api/properties/  -> list available properties (cached in Redis)
         optional filters: ?city=  ?min_rent=  ?max_rent=  ?bedrooms=  ?amenity=<id>
    POST /api/properties/  -> create a property (owners only)
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsOwnerRole()]
        return [IsAuthenticated()]

    @extend_schema(
        tags=["Properties"],
        parameters=[
            OpenApiParameter("city", str, description="City contains this text"),
            OpenApiParameter("min_rent", float, description="Minimum monthly rent"),
            OpenApiParameter("max_rent", float, description="Maximum monthly rent"),
            OpenApiParameter("bedrooms", int, description="Exact number of bedrooms"),
            OpenApiParameter("amenity", int, description="Amenity id"),
        ],
        responses={200: PropertySerializer(many=True), 400: ErrorSerializer},
    )
    def get(self, request):
        # 1) Build a cache key from the version number + the filters in the URL
        query_string = request.META.get("QUERY_STRING", "")
        query_hash = hashlib.md5(query_string.encode()).hexdigest()
        cache_key = f"properties:v{get_cache_version()}:{query_hash}"

        # 2) If the answer is already in Redis, return it (no database query)
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data, headers={"X-Cache": "HIT"})

        # 3) Otherwise read from the database, applying the filters
        properties = Property.objects.filter(is_available=True)
        params = request.query_params
        try:
            if params.get("city"):
                properties = properties.filter(city__icontains=params["city"])
            if params.get("min_rent"):
                properties = properties.filter(rent_amount__gte=params["min_rent"])
            if params.get("max_rent"):
                properties = properties.filter(rent_amount__lte=params["max_rent"])
            if params.get("bedrooms"):
                properties = properties.filter(bedrooms=params["bedrooms"])
            if params.get("amenity"):
                properties = properties.filter(amenities__id=params["amenity"])
        except (ValueError, DjangoValidationError):
            return Response({"error": "A filter value is not valid."}, status=status.HTTP_400_BAD_REQUEST)

        # select_related / prefetch_related load the related rows in fewer queries
        properties = properties.select_related("owner__profile").prefetch_related("amenities")
        data = PropertySerializer(properties, many=True).data

        # 4) Save the answer in Redis for 5 minutes
        cache.set(cache_key, data, timeout=300)
        return Response(data, headers={"X-Cache": "MISS"})

    @extend_schema(tags=["Properties"], request=PropertySerializer, responses={201: PropertySerializer})
    def post(self, request):
        serializer = PropertySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)  # the owner is the logged-in user
        bump_cache_version()  # the list changed, so old cached lists must not be used
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MyPropertiesView(APIView):
    """GET /api/my-properties/  -> all properties of the logged-in owner (rented ones too)."""

    permission_classes = [IsAuthenticated, IsOwnerRole]

    @extend_schema(tags=["Properties"], responses=PropertySerializer(many=True))
    def get(self, request):
        properties = (
            Property.objects.filter(owner=request.user)
            .select_related("owner__profile")
            .prefetch_related("amenities")
        )
        return Response(PropertySerializer(properties, many=True).data)


class PropertyDetailView(APIView):
    """
    GET    /api/properties/<id>/  -> see one property
    PUT    /api/properties/<id>/  -> change a property (only its owner)
    PATCH  /api/properties/<id>/  -> change only some fields (only its owner)
    DELETE /api/properties/<id>/  -> delete a property (only its owner)
    """

    def get_property(self, pk):
        """Find the property or return a 404 error."""
        return get_object_or_404(
            Property.objects.select_related("owner__profile").prefetch_related("amenities"), pk=pk
        )

    @extend_schema(tags=["Properties"], responses=PropertySerializer)
    def get(self, request, pk):
        return Response(PropertySerializer(self.get_property(pk)).data)

    def update_property(self, request, pk, partial):
        """Shared code for PUT (all fields) and PATCH (some fields)."""
        rental = self.get_property(pk)
        if rental.owner != request.user:
            return Response({"error": "You do not own this property."}, status=status.HTTP_403_FORBIDDEN)
        serializer = PropertySerializer(rental, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        bump_cache_version()
        return Response(serializer.data)

    @extend_schema(tags=["Properties"], request=PropertySerializer, responses={200: PropertySerializer, 403: ErrorSerializer})
    def put(self, request, pk):
        return self.update_property(request, pk, partial=False)

    @extend_schema(tags=["Properties"], request=PropertySerializer, responses={200: PropertySerializer, 403: ErrorSerializer})
    def patch(self, request, pk):
        return self.update_property(request, pk, partial=True)

    @extend_schema(tags=["Properties"], responses={204: None, 403: ErrorSerializer})
    def delete(self, request, pk):
        rental = self.get_property(pk)
        if rental.owner != request.user:
            return Response({"error": "You do not own this property."}, status=status.HTTP_403_FORBIDDEN)
        rental.delete()
        bump_cache_version()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LeaseListCreateView(APIView):
    """
    GET  /api/leases/  -> owners see leases of their properties, tenants see their own leases
    POST /api/leases/  -> an owner creates a lease for one of their properties
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsOwnerRole()]
        return [IsAuthenticated()]

    @extend_schema(tags=["Leases"], responses=LeaseSerializer(many=True))
    def get(self, request):
        leases = Lease.objects.select_related("property", "tenant__profile")
        if request.user.role == "owner":
            leases = leases.filter(property__owner=request.user)
        else:
            leases = leases.filter(tenant=request.user)
        return Response(LeaseSerializer(leases, many=True, context={"request": request}).data)

    @extend_schema(tags=["Leases"], request=LeaseSerializer, responses={201: LeaseSerializer})
    def post(self, request):
        serializer = LeaseSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        lease = serializer.save()

        bump_cache_version()                # the property is not available anymore
        send_lease_email.delay(lease.id)    # tell the tenant by email (background task)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LeaseDetailView(APIView):
    """GET /api/leases/<id>/  -> one lease (only its tenant or the property's owner can see it)."""

    @extend_schema(tags=["Leases"], responses={200: LeaseSerializer, 403: ErrorSerializer})
    def get(self, request, pk):
        lease = get_object_or_404(Lease.objects.select_related("property", "tenant__profile"), pk=pk)
        if request.user != lease.tenant and request.user != lease.property.owner:
            return Response({"error": "You cannot see this lease."}, status=status.HTTP_403_FORBIDDEN)
        return Response(LeaseSerializer(lease, context={"request": request}).data)


class LeaseEndView(APIView):
    """POST /api/leases/<id>/end/  -> the owner ends a lease early; the property becomes available."""

    permission_classes = [IsAuthenticated, IsOwnerRole]

    @extend_schema(tags=["Leases"], request=None, responses={200: LeaseSerializer, 400: ErrorSerializer, 403: ErrorSerializer})
    def post(self, request, pk):
        lease = get_object_or_404(Lease.objects.select_related("property", "tenant__profile"), pk=pk)
        if lease.property.owner != request.user:
            return Response({"error": "You do not own this property."}, status=status.HTTP_403_FORBIDDEN)
        if not lease.is_active:
            return Response({"error": "This lease is already ended."}, status=status.HTTP_400_BAD_REQUEST)

        lease.is_active = False
        lease.save()
        lease.property.is_available = True
        lease.property.save()
        bump_cache_version()
        return Response(LeaseSerializer(lease, context={"request": request}).data)



class LeaseRequestListCreateView(APIView):
    """
    GET  /api/lease-requests/  -> tenants see their own requests, owners see requests for their properties
                                  optional filter: ?status=pending
    POST /api/lease-requests/  -> a tenant asks to rent a property
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsTenantRole()]
        return [IsAuthenticated()]

    @extend_schema(
        tags=["Lease requests"],
        parameters=[OpenApiParameter("status", str, description="pending, approved, rejected or cancelled")],
        responses=LeaseRequestSerializer(many=True),
    )
    def get(self, request):
        requests = LeaseRequest.objects.select_related("property", "tenant__profile")
        if request.user.role == "owner":
            requests = requests.filter(property__owner=request.user)
        else:
            requests = requests.filter(tenant=request.user)
        if request.query_params.get("status"):
            requests = requests.filter(status=request.query_params["status"])
        return Response(LeaseRequestSerializer(requests, many=True, context={"request": request}).data)

    @extend_schema(tags=["Lease requests"], request=LeaseRequestSerializer, responses={201: LeaseRequestSerializer})
    def post(self, request):
        serializer = LeaseRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        lease_request = serializer.save(tenant=request.user)  # the tenant is the logged-in user
        send_request_status_email.delay(lease_request.id)     # tell the owner by email
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LeaseRequestDetailView(APIView):
    """GET /api/lease-requests/<id>/  -> one request (only its tenant or the property's owner)."""

    @extend_schema(tags=["Lease requests"], responses={200: LeaseRequestSerializer, 403: ErrorSerializer})
    def get(self, request, pk):
        lease_request = get_object_or_404(LeaseRequest.objects.select_related("property", "tenant__profile"), pk=pk)
        if request.user != lease_request.tenant and request.user != lease_request.property.owner:
            return Response({"error": "You cannot see this request."}, status=status.HTTP_403_FORBIDDEN)
        return Response(LeaseRequestSerializer(lease_request, context={"request": request}).data)


class LeaseRequestApproveView(APIView):
    
    """
    POST /api/lease-requests/<id>/approve/  -> the owner accepts the request.
    A Lease is created, the property becomes unavailable, and other pending requests
    for the same property are rejected.
    """

    permission_classes = [IsAuthenticated, IsOwnerRole]

    @extend_schema(
        tags=["Lease requests"],
        request=None,
        responses={200: LeaseRequestSerializer, 400: ErrorSerializer, 403: ErrorSerializer},
    )
    def post(self, request, pk):
        lease_request = get_object_or_404(LeaseRequest.objects.select_related("property", "tenant__profile"), pk=pk)
        rental = lease_request.property

        if rental.owner != request.user:
            return Response({"error": "You do not own this property."}, status=status.HTTP_403_FORBIDDEN)
        if lease_request.status != "pending":
            return Response({"error": "Only pending requests can be approved."}, status=status.HTTP_400_BAD_REQUEST)
        if not rental.is_available:
            return Response({"error": "This property is already rented."}, status=status.HTTP_400_BAD_REQUEST)

        # Do all the database changes together: either all succeed or none
        with transaction.atomic():
            lease = Lease.objects.create(
                property=rental,
                tenant=lease_request.tenant,
                start_date=lease_request.start_date,
                end_date=lease_request.end_date,
                monthly_rent=rental.rent_amount,
            )
            rental.is_available = False
            rental.save()

            lease_request.status = "approved"
            lease_request.lease = lease
            lease_request.save()

            # Nobody else can rent it now, so reject the other pending requests
            LeaseRequest.objects.filter(property=rental, status="pending").exclude(pk=lease_request.pk).update(
                status="rejected"
            )

        bump_cache_version()                                  # the property list changed
        send_request_status_email.delay(lease_request.id)     # tell the tenant by email
        return Response(LeaseRequestSerializer(lease_request, context={"request": request}).data)


class LeaseRequestRejectView(APIView):
    """POST /api/lease-requests/<id>/reject/  -> the owner rejects the request."""

    permission_classes = [IsAuthenticated, IsOwnerRole]

    @extend_schema(
        tags=["Lease requests"],
        request=None,
        responses={200: LeaseRequestSerializer, 400: ErrorSerializer, 403: ErrorSerializer},
    )
    def post(self, request, pk):
        lease_request = get_object_or_404(LeaseRequest.objects.select_related("property", "tenant__profile"), pk=pk)

        if lease_request.property.owner != request.user:
            return Response({"error": "You do not own this property."}, status=status.HTTP_403_FORBIDDEN)
        if lease_request.status != "pending":
            return Response({"error": "Only pending requests can be rejected."}, status=status.HTTP_400_BAD_REQUEST)

        lease_request.status = "rejected"
        lease_request.save()
        send_request_status_email.delay(lease_request.id)     # tell the tenant by email
        return Response(LeaseRequestSerializer(lease_request, context={"request": request}).data)


class LeaseRequestCancelView(APIView):
    """POST /api/lease-requests/<id>/cancel/  -> the tenant withdraws their own pending request."""

    permission_classes = [IsAuthenticated, IsTenantRole]

    @extend_schema(
        tags=["Lease requests"],
        request=None,
        responses={200: LeaseRequestSerializer, 400: ErrorSerializer, 403: ErrorSerializer},
    )
    def post(self, request, pk):
        lease_request = get_object_or_404(LeaseRequest.objects.select_related("property", "tenant__profile"), pk=pk)

        if lease_request.tenant != request.user:
            return Response({"error": "This is not your request."}, status=status.HTTP_403_FORBIDDEN)
        if lease_request.status != "pending":
            return Response({"error": "Only pending requests can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)

        lease_request.status = "cancelled"
        lease_request.save()
        return Response(LeaseRequestSerializer(lease_request, context={"request": request}).data)