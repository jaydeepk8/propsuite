"""django-filter FilterSet for leases."""

import django_filters
from django import forms

from .models import Lease


class LeaseFilter(django_filters.FilterSet):
    """Filter leases by status."""

    status = django_filters.ChoiceFilter(
        choices=Lease.Status.choices,
        empty_label="All statuses",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Lease
        fields = ["status"]
