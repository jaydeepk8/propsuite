"""django-filter FilterSet for expenses."""

import django_filters
from django import forms

from properties.models import Property
from .models import Expense


class ExpenseFilter(django_filters.FilterSet):
    category = django_filters.ChoiceFilter(
        choices=Expense.Category.choices,
        empty_label="All categories",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    property = django_filters.ModelChoiceFilter(
        queryset=Property.objects.none(),   # narrowed to the owner in __init__
        empty_label="All properties",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Expense
        fields = ["category", "property"]

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Property.objects.for_user(owner) if owner else Property.objects.none()
        self.filters["property"].queryset = qs
