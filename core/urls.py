"""Main URL list. Each app has its own urls.py that we include here."""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),  # register, login, password reset ...
    path("api/", include("rentals.urls")),        # properties, amenities, leases
    # Swagger documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),  # the raw OpenAPI file
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),  # the Swagger page
]
