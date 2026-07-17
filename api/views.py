"""
DRF viewsets for the PropSuite API.

Every viewset reuses the same `for_user` querysets as the web app, so the API
enforces exactly the same ownership rules. JWT auth and the default filter
backends come from REST_FRAMEWORK settings.
"""

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from inspections.models import Inspection
from leases.models import Lease
from maintenance.models import MaintenanceRequest
from notifications.models import Notification
from payments.models import RentPayment
from properties.models import Property, Unit
from tenants.models import Tenant
from .permissions import IsOwnerOrAdmin, IsOwnerOrAdminOrReadOnly
from .serializers import (
    InspectionSerializer, LeaseSerializer, MaintenanceRequestSerializer,
    NotificationSerializer, PropertySerializer, RentPaymentSerializer,
    TenantSerializer, UnitSerializer, UserSerializer,
)


class MeView(APIView):
    """Return the authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class PropertyViewSet(viewsets.ModelViewSet):
    serializer_class = PropertySerializer
    permission_classes = [IsOwnerOrAdmin]
    filterset_fields = ["property_type", "status", "city"]
    search_fields = ["title", "address", "city"]
    ordering_fields = ["created_at", "title"]

    def get_queryset(self):
        return Property.objects.for_user(self.request.user).with_owner()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class UnitViewSet(viewsets.ModelViewSet):
    serializer_class = UnitSerializer
    permission_classes = [IsOwnerOrAdmin]
    filterset_fields = ["status", "bedrooms", "property"]
    search_fields = ["unit_number", "property__title"]

    def get_queryset(self):
        return Unit.objects.filter(
            property__in=Property.objects.for_user(self.request.user)
        ).select_related("property")


class TenantViewSet(viewsets.ModelViewSet):
    serializer_class = TenantSerializer
    permission_classes = [IsOwnerOrAdmin]
    search_fields = ["user__first_name", "user__last_name", "user__email", "occupation"]

    def get_queryset(self):
        return Tenant.objects.for_user(self.request.user).select_related("user")


class LeaseViewSet(viewsets.ModelViewSet):
    serializer_class = LeaseSerializer
    permission_classes = [IsOwnerOrAdmin]
    filterset_fields = ["status"]
    search_fields = ["tenant__user__first_name", "unit__unit_number", "unit__property__title"]

    def get_queryset(self):
        return Lease.objects.for_user(self.request.user).select_related(
            "tenant__user", "unit__property")


class RentPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = RentPaymentSerializer
    permission_classes = [IsOwnerOrAdmin]
    filterset_fields = ["status", "month", "year"]
    search_fields = ["lease__tenant__user__first_name", "lease__unit__property__title"]
    ordering_fields = ["year", "month", "due_date"]

    def get_queryset(self):
        return RentPayment.objects.for_user(self.request.user).select_related(
            "lease__tenant__user", "lease__unit__property")

    @action(detail=True, methods=["post"])
    def mark_paid(self, request, pk=None):
        """POST /api/payments/{id}/mark_paid/ — record a payment as paid."""
        payment = self.get_object()
        payment.mark_paid(
            method=request.data.get("payment_method") or None,
            when=request.data.get("payment_date") or None,
        )
        return Response(self.get_serializer(payment).data)


class MaintenanceRequestViewSet(viewsets.ModelViewSet):
    """Tenants may create and view their own; owners manage all of theirs."""

    serializer_class = MaintenanceRequestSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "priority"]
    search_fields = ["title", "description", "unit__unit_number"]

    def get_queryset(self):
        return MaintenanceRequest.objects.for_user(self.request.user).select_related(
            "unit__property", "tenant__user")

    def perform_create(self, serializer):
        user = self.request.user
        extra = {"created_by": user}
        if user.is_tenant:
            extra["tenant"] = getattr(user, "tenant_profile", None)
        else:
            active = (Lease.objects.filter(unit=serializer.validated_data["unit"],
                                           status=Lease.Status.ACTIVE)
                      .select_related("tenant").first())
            extra["tenant"] = active.tenant if active else None
        serializer.save(**extra)


class InspectionViewSet(viewsets.ModelViewSet):
    serializer_class = InspectionSerializer
    permission_classes = [IsOwnerOrAdmin]
    filterset_fields = ["status"]
    search_fields = ["property__title", "unit__unit_number", "notes"]

    def get_queryset(self):
        return Inspection.objects.for_user(self.request.user).select_related(
            "property", "unit", "inspector")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list/detail plus mark-read actions."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["is_read", "kind"]

    def get_queryset(self):
        return Notification.objects.for_user(self.request.user)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_read()
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"])
    def read_all(self, request):
        count = self.get_queryset().unread().update(is_read=True)
        return Response({"marked_read": count}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        return Response({"unread": self.get_queryset().unread().count()})
