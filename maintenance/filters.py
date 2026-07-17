"""django-filter FilterSet for maintenance requests."""

import django_filters
from django import forms

from .models import MaintenanceRequest


class MaintenanceFilter(django_filters.FilterSet):
    """Filter maintenance requests by status and priority."""

    status = django_filters.ChoiceFilter(
        choices=MaintenanceRequest.Status.choices,
        empty_label="All statuses",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    priority = django_filters.ChoiceFilter(
        choices=MaintenanceRequest.Priority.choices,
        empty_label="All priorities",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = MaintenanceRequest
        fields = ["status", "priority"]
