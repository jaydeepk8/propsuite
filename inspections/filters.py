"""django-filter FilterSet for inspections."""

import django_filters
from django import forms

from .models import Inspection


class InspectionFilter(django_filters.FilterSet):
    """Filter inspections by status."""

    status = django_filters.ChoiceFilter(
        choices=Inspection.Status.choices,
        empty_label="All statuses",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Inspection
        fields = ["status"]
