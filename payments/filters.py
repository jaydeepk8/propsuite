"""django-filter FilterSet for rent payments."""

import django_filters
from django import forms
from django.utils import timezone

from .models import MONTH_CHOICES, RentPayment


class RentPaymentFilter(django_filters.FilterSet):
    """
    Filter payments by month, year, property, tenant and status.

    `status` is special: PAID/PENDING map to the stored field, while OVERDUE
    is computed (pending + past due date).
    """

    STATUS_CHOICES = [("PAID", "Paid"), ("PENDING", "Pending"), ("OVERDUE", "Overdue")]

    month = django_filters.ChoiceFilter(
        choices=MONTH_CHOICES, empty_label="Any month",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    year = django_filters.NumberFilter(
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Year"}),
    )
    property = django_filters.NumberFilter(
        field_name="lease__unit__property_id",
        widget=forms.HiddenInput(),
    )
    tenant = django_filters.NumberFilter(
        field_name="lease__tenant_id",
        widget=forms.HiddenInput(),
    )
    status = django_filters.ChoiceFilter(
        choices=STATUS_CHOICES, method="filter_status", empty_label="Any status",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = RentPayment
        fields = ["month", "year", "property", "tenant", "status"]

    def filter_status(self, queryset, name, value):
        if value == "OVERDUE":
            return queryset.overdue()
        if value == "PAID":
            return queryset.paid()
        if value == "PENDING":
            # "Pending" here means still-pending but not yet overdue.
            return queryset.pending().filter(due_date__gte=timezone.localdate())
        return queryset
