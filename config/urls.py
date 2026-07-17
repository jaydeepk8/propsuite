"""
Root URL configuration for PropSuite.

App URLconfs are included here as each milestone is built. In development,
user-uploaded media is served by Django (see MEDIA settings below).
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django's own admin lives under /django-admin/ so the PropSuite admin
    # dashboard can own the natural /admin/ route (also a small hardening win).
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("properties/", include("properties.urls")),
    path("tenants/", include("tenants.urls")),
    path("leases/", include("leases.urls")),
    path("payments/", include("payments.urls")),
    path("maintenance/", include("maintenance.urls")),
    path("inspections/", include("inspections.urls")),
    path("expenses/", include("expenses.urls")),
    path("notifications/", include("notifications.urls")),
    path("api/", include("api.urls")),
    path("", include("dashboard.urls")),
    # Added per milestone:
    #   path("api/", include("api.urls")),
]

# Serve uploaded media files during development only.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
