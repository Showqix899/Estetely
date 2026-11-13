from django.urls import path

from .views import (
    AmenityListCreateView,
    LeaseDetailView,
    LeaseEndView,
    LeaseListCreateView,
    MyPropertiesView,
    PropertyDetailView,
    PropertyListCreateView,
)

urlpatterns = [
    path("amenities/", AmenityListCreateView.as_view()),
    path("properties/", PropertyListCreateView.as_view()),
    path("properties/<int:pk>/", PropertyDetailView.as_view()),
    path("my-properties/", MyPropertiesView.as_view()),
    path("leases/", LeaseListCreateView.as_view()),
    path("leases/<int:pk>/", LeaseDetailView.as_view()),
    path("leases/<int:pk>/end/", LeaseEndView.as_view()),
]
