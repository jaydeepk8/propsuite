"""Forms for raising and managing maintenance requests."""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row
from django import forms
from django.contrib.auth import get_user_model

from properties.models import Property, Unit
from .models import MaintenanceRequest

User = get_user_model()


class MaintenanceRequestForm(forms.ModelForm):
    """
    Raise or edit a request. Unit choices depend on the user's role:
      * tenants pick from units they lease
      * owners/admins pick from units they manage
    """

    class Meta:
        model = MaintenanceRequest
        fields = ("unit", "title", "description", "priority", "image")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user is not None:
            self.fields["unit"].queryset = self._unit_choices(user)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            "unit",
            "title",
            "description",
            Row(
                Column("priority", css_class="col-md-6"),
                Column("image", css_class="col-md-6"),
            ),
        )

    @staticmethod
    def _unit_choices(user):
        if user.is_admin:
            return Unit.objects.select_related("property").all()
        if user.is_owner:
            return Unit.objects.filter(
                property__in=Property.objects.for_user(user)
            ).select_related("property")
        # Tenant — only units they lease.
        profile = getattr(user, "tenant_profile", None)
        if profile is None:
            return Unit.objects.none()
        return Unit.objects.filter(leases__tenant=profile).select_related("property").distinct()


class MaintenanceManageForm(forms.ModelForm):
    """Owner/admin form to assign a request and move its status forward."""

    class Meta:
        model = MaintenanceRequest
        fields = ("status", "assigned_to", "estimated_cost", "completed_date")
        widgets = {"completed_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Requests can be assigned to owners or admins.
        self.fields["assigned_to"].queryset = User.objects.filter(
            role__in=[User.Roles.OWNER, User.Roles.ADMIN]
        )
        self.fields["assigned_to"].required = False

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("status", css_class="col-md-6"),
                Column("assigned_to", css_class="col-md-6"),
            ),
            Row(
                Column("estimated_cost", css_class="col-md-6"),
                Column("completed_date", css_class="col-md-6"),
            ),
        )
