"""Tenant onboarding/edit form (manages the linked User too)."""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row
from django import forms
from django.contrib.auth import get_user_model

from .models import Tenant

User = get_user_model()


class TenantForm(forms.ModelForm):
    """
    Create or edit a tenant. On create it also provisions a User account
    (role=Tenant) with an unusable password — the tenant sets their own via
    the "Forgot password" flow.
    """

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField()

    class Meta:
        model = Tenant
        fields = ("phone", "emergency_contact", "aadhaar_number", "occupation")

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

        # Pre-fill user fields when editing an existing tenant.
        if self.instance and self.instance.pk:
            u = self.instance.user
            self.fields["first_name"].initial = u.first_name
            self.fields["last_name"].initial = u.last_name
            self.fields["email"].initial = u.email

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("first_name", css_class="col-md-6"),
                Column("last_name", css_class="col-md-6"),
            ),
            Row(
                Column("email", css_class="col-md-6"),
                Column("phone", css_class="col-md-6"),
            ),
            Row(
                Column("occupation", css_class="col-md-6"),
                Column("emergency_contact", css_class="col-md-6"),
            ),
            "aadhaar_number",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        tenant = super().save(commit=False)
        cd = self.cleaned_data

        if tenant.pk and tenant.user_id:
            # Editing — update the linked user's details.
            user = tenant.user
            user.first_name = cd["first_name"]
            user.last_name = cd["last_name"]
            user.email = cd["email"]
            user.save()
        else:
            # Creating — provision the tenant's user account.
            user = User(
                username=cd["email"],
                email=cd["email"],
                first_name=cd["first_name"],
                last_name=cd["last_name"],
                role=User.Roles.TENANT,
            )
            user.set_unusable_password()
            user.save()
            tenant.user = user
            tenant.created_by = self.owner

        if commit:
            tenant.save()
        return tenant
