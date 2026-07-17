"""django-filter FilterSet for tenants."""

import django_filters
from django import forms

from .models import Tenant


class TenantFilter(django_filters.FilterSet):
    """Filter tenants by occupation (search handled separately in the view)."""

    occupation = django_filters.CharFilter(
        lookup_expr="icontains",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Any occupation"}),
    )

    class Meta:
        model = Tenant
        fields = ["occupation"]
