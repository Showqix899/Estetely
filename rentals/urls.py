from django.urls import path

from .views import (
    AmenityListCreateView,
    LeaseDetailView,
    LeaseEndView,
    LeaseListCreateView,
    MyPropertiesView,
    PropertyDetailView,
    PropertyListCreateView,
    LeaseRequestApproveView,
    LeaseRequestCancelView,
    LeaseRequestDetailView,
    LeaseRequestListCreateView,
    LeaseRequestRejectView,
)

urlpatterns = [
    path("amenities/", AmenityListCreateView.as_view()),
    path("properties/", PropertyListCreateView.as_view()),
    path("properties/<int:pk>/", PropertyDetailView.as_view()),
    path("my-properties/", MyPropertiesView.as_view()),
    path("leases/", LeaseListCreateView.as_view()),
    path("leases/<int:pk>/", LeaseDetailView.as_view()),
    path("leases/<int:pk>/end/", LeaseEndView.as_view()),
    path("lease-requests/", LeaseRequestListCreateView.as_view()),
    path("lease-requests/<int:pk>/", LeaseRequestDetailView.as_view()),
    path("lease-requests/<int:pk>/approve/", LeaseRequestApproveView.as_view()),
    path("lease-requests/<int:pk>/reject/", LeaseRequestRejectView.as_view()),
    path("lease-requests/<int:pk>/cancel/", LeaseRequestCancelView.as_view()),
]
