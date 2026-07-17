"""DRF serializers for the PropSuite API."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from inspections.models import Inspection
from leases.models import Lease
from maintenance.models import MaintenanceRequest
from notifications.models import Notification
from payments.models import RentPayment
from properties.models import Property, Unit
from tenants.models import Tenant

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "full_name", "role", "phone")
        read_only_fields = ("id", "role")


# ── Properties & Units ──────────────────────────────────
class PropertySerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)
    property_type_display = serializers.CharField(source="get_property_type_display", read_only=True)
    units_count = serializers.IntegerField(read_only=True)
    occupied_count = serializers.IntegerField(read_only=True)
    vacant_count = serializers.IntegerField(read_only=True)
    monthly_income = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Property
        fields = (
            "id", "owner", "title", "description", "property_type",
            "property_type_display", "status", "address", "city", "state",
            "country", "pincode", "image", "total_units", "units_count",
            "occupied_count", "vacant_count", "monthly_income", "created_at",
        )
        read_only_fields = ("id", "owner", "created_at")


class UnitSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source="property.title", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Unit
        fields = (
            "id", "property", "property_title", "unit_number", "floor",
            "bedrooms", "bathrooms", "rent_amount", "security_deposit",
            "status", "status_display",
        )
        read_only_fields = ("id",)

    def validate_property(self, value):
        # A user may only attach units to properties they own.
        request = self.context["request"]
        if value not in Property.objects.for_user(request.user):
            raise serializers.ValidationError("You don't own that property.")
        return value


# ── Tenants ─────────────────────────────────────────────
class TenantSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    masked_aadhaar = serializers.CharField(read_only=True)

    # Write-only fields to provision the linked user on create.
    first_name = serializers.CharField(write_only=True, required=False)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    email_address = serializers.EmailField(write_only=True, required=False)

    class Meta:
        model = Tenant
        fields = (
            "id", "user", "full_name", "email", "phone", "emergency_contact",
            "aadhaar_number", "occupation", "masked_aadhaar", "created_at",
            "first_name", "last_name", "email_address",
        )
        read_only_fields = ("id", "user", "created_at")
        extra_kwargs = {"aadhaar_number": {"write_only": True}}

    def validate_email_address(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        first = validated_data.pop("first_name", "")
        last = validated_data.pop("last_name", "")
        email = validated_data.pop("email_address", None)
        if not (first and email):
            raise serializers.ValidationError(
                {"first_name": "first_name and email_address are required to create a tenant."})

        user = User(username=email, email=email, first_name=first,
                    last_name=last, role=User.Roles.TENANT)
        user.set_unusable_password()
        user.save()
        validated_data["user"] = user
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


# ── Leases ──────────────────────────────────────────────
class LeaseSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.full_name", read_only=True)
    unit_label = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Lease
        fields = (
            "id", "tenant", "tenant_name", "unit", "unit_label",
            "start_date", "end_date", "monthly_rent", "security_deposit",
            "status", "status_display",
        )
        read_only_fields = ("id",)

    def get_unit_label(self, obj):
        return f"{obj.unit.property.title} · {obj.unit.unit_number}"

    def validate(self, attrs):
        request = self.context["request"]
        tenant = attrs.get("tenant") or getattr(self.instance, "tenant", None)
        unit = attrs.get("unit") or getattr(self.instance, "unit", None)

        if tenant and tenant not in Tenant.objects.for_user(request.user):
            raise serializers.ValidationError({"tenant": "Not one of your tenants."})
        if unit and unit not in Unit.objects.filter(
                property__in=Property.objects.for_user(request.user)):
            raise serializers.ValidationError({"unit": "Not one of your units."})

        start = attrs.get("start_date") or getattr(self.instance, "start_date", None)
        end = attrs.get("end_date") or getattr(self.instance, "end_date", None)
        if start and end and end <= start:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})
        return attrs


# ── Payments ────────────────────────────────────────────
class RentPaymentSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="lease.tenant.full_name", read_only=True)
    effective_status = serializers.CharField(read_only=True)
    total_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    receipt_number = serializers.CharField(read_only=True)

    class Meta:
        model = RentPayment
        fields = (
            "id", "lease", "tenant_name", "month", "year", "due_date",
            "payment_date", "amount", "late_fee", "payment_method", "status",
            "effective_status", "total_due", "receipt_number",
        )
        read_only_fields = ("id",)

    def validate_lease(self, value):
        request = self.context["request"]
        if value not in Lease.objects.for_user(request.user):
            raise serializers.ValidationError("Not one of your leases.")
        return value


# ── Maintenance ─────────────────────────────────────────
class MaintenanceRequestSerializer(serializers.ModelSerializer):
    unit_label = serializers.SerializerMethodField()
    tenant_name = serializers.CharField(source="tenant.full_name", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = MaintenanceRequest
        fields = (
            "id", "unit", "unit_label", "tenant", "tenant_name", "title",
            "description", "priority", "priority_display", "status",
            "status_display", "assigned_to", "estimated_cost",
            "completed_date", "image", "created_at",
        )
        read_only_fields = ("id", "tenant", "created_at")

    def get_unit_label(self, obj):
        return f"{obj.unit.property.title} · {obj.unit.unit_number}"

    def validate_unit(self, value):
        request = self.context["request"]
        user = request.user
        if user.is_owner or user.is_admin:
            allowed = Unit.objects.filter(property__in=Property.objects.for_user(user))
        else:
            profile = getattr(user, "tenant_profile", None)
            allowed = (Unit.objects.filter(leases__tenant=profile).distinct()
                       if profile else Unit.objects.none())
        if value not in allowed:
            raise serializers.ValidationError("You can't raise a request against that unit.")
        return value


# ── Inspections ─────────────────────────────────────────
class InspectionSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source="property.title", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Inspection
        fields = (
            "id", "property", "property_title", "unit", "inspector",
            "inspection_date", "notes", "report", "status", "status_display",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        request = self.context["request"]
        prop = attrs.get("property") or getattr(self.instance, "property", None)
        unit = attrs.get("unit") or getattr(self.instance, "unit", None)
        if prop and prop not in Property.objects.for_user(request.user):
            raise serializers.ValidationError({"property": "Not one of your properties."})
        if unit and prop and unit.property_id != prop.pk:
            raise serializers.ValidationError({"unit": "Unit doesn't belong to that property."})
        return attrs


# ── Notifications ───────────────────────────────────────
class NotificationSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = Notification
        fields = ("id", "title", "message", "url", "kind", "kind_display",
                  "is_read", "created_at")
        read_only_fields = ("id", "title", "message", "url", "kind", "created_at")
