"""django-filter FilterSets for the properties module."""

import django_filters
from django import forms

from .models import Property, Unit


class PropertyFilter(django_filters.FilterSet):
    """Filter properties by city, type and status (spec: City, Type)."""

    city = django_filters.CharFilter(
        lookup_expr="icontains",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Any city"}),
    )
    property_type = django_filters.ChoiceFilter(
        choices=Property.PropertyType.choices,
        empty_label="All types",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = django_filters.ChoiceFilter(
        choices=Property.Status.choices,
        empty_label="All statuses",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Property
        fields = ["city", "property_type", "status"]


class UnitFilter(django_filters.FilterSet):
    """Filter units by status and bedrooms."""

    status = django_filters.ChoiceFilter(
        choices=Unit.Status.choices,
        empty_label="All statuses",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Unit
        fields = ["status", "bedrooms"]
