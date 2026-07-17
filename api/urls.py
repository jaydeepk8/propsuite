"""API URL configuration — router + JWT auth endpoints."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView, TokenVerifyView,
)

from . import views

app_name = "api"

router = DefaultRouter()
router.register("properties", views.PropertyViewSet, basename="property")
router.register("units", views.UnitViewSet, basename="unit")
router.register("tenants", views.TenantViewSet, basename="tenant")
router.register("leases", views.LeaseViewSet, basename="lease")
router.register("payments", views.RentPaymentViewSet, basename="payment")
router.register("maintenance", views.MaintenanceRequestViewSet, basename="maintenance")
router.register("inspections", views.InspectionViewSet, basename="inspection")
router.register("notifications", views.NotificationViewSet, basename="notification")

urlpatterns = [
    # JWT authentication
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # Current user
    path("me/", views.MeView.as_view(), name="me"),

    # Resource endpoints
    path("", include(router.urls)),
]
