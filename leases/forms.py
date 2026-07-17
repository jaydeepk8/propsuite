"""Lease form with owner-scoped choices and business-rule validation."""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row
from django import forms

from properties.models import Unit
from tenants.models import Tenant
from .models import Lease


class LeaseForm(forms.ModelForm):
    """
    Create/edit a lease. Tenant and unit choices are scoped to the current
    owner, and (per spec) a tenant may only be assigned to an *available*
    unit — the unit dropdown is filtered accordingly.
    """

    class Meta:
        model = Lease
        fields = ("tenant", "unit", "start_date", "end_date",
                  "monthly_rent", "security_deposit", "status")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Scope tenant choices to this owner.
        if owner is not None:
            self.fields["tenant"].queryset = Tenant.objects.for_user(owner)

            # Available units for this owner, plus the currently-linked unit
            # when editing (so it stays selectable even though it's occupied).
            unit_qs = Unit.objects.filter(status=Unit.Status.AVAILABLE)
            if not owner.is_admin:
                unit_qs = unit_qs.filter(property__owner=owner)
            if self.instance and self.instance.pk:
                unit_qs = unit_qs | Unit.objects.filter(pk=self.instance.unit_id)
            self.fields["unit"].queryset = unit_qs.select_related("property").distinct()

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("tenant", css_class="col-md-6"),
                Column("unit", css_class="col-md-6"),
            ),
            Row(
                Column("start_date", css_class="col-md-6"),
                Column("end_date", css_class="col-md-6"),
            ),
            Row(
                Column("monthly_rent", css_class="col-md-6"),
                Column("security_deposit", css_class="col-md-6"),
            ),
            "status",
        )

    def clean(self):
        cleaned = super().clean()
        unit = cleaned.get("unit")
        status = cleaned.get("status")

        # Guard: an ACTIVE lease can't be created on a unit already occupied
        # by a *different* active lease.
        if unit and status == Lease.Status.ACTIVE:
            clash = Lease.objects.filter(
                unit=unit, status=Lease.Status.ACTIVE
            ).exclude(pk=self.instance.pk)
            if clash.exists():
                raise forms.ValidationError(
                    "That unit already has an active lease."
                )
        return cleaned
