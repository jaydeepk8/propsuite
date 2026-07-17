"""Forms for recording and editing rent payments."""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row
from django import forms
from django.utils import timezone

from leases.models import Lease
from .models import RentPayment


class RentPaymentForm(forms.ModelForm):
    """Record or edit a rent payment. Lease choices are scoped to the owner."""

    class Meta:
        model = RentPayment
        fields = ("lease", "month", "year", "due_date", "amount",
                  "late_fee", "status", "payment_method", "payment_date")
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "payment_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Scope lease choices; owners only see leases on their own units.
        if owner is not None:
            self.fields["lease"].queryset = (
                Lease.objects.for_user(owner)
                .select_related("tenant__user", "unit__property")
            )

        # Sensible defaults for a fresh record.
        if not self.instance.pk:
            today = timezone.localdate()
            self.fields["year"].initial = today.year
            self.fields["month"].initial = today.month

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            "lease",
            Row(
                Column("month", css_class="col-md-4"),
                Column("year", css_class="col-md-4"),
                Column("due_date", css_class="col-md-4"),
            ),
            Row(
                Column("amount", css_class="col-md-6"),
                Column("late_fee", css_class="col-md-6"),
            ),
            Row(
                Column("status", css_class="col-md-4"),
                Column("payment_method", css_class="col-md-4"),
                Column("payment_date", css_class="col-md-4"),
            ),
        )

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        # A paid record should carry a payment date; default it to today.
        if status == RentPayment.Status.PAID and not cleaned.get("payment_date"):
            cleaned["payment_date"] = timezone.localdate()
        return cleaned


class MarkPaidForm(forms.Form):
    """Lightweight form for the "record payment" quick action."""

    payment_method = forms.ChoiceField(choices=RentPayment.Method.choices)
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
    )
    late_fee = forms.DecimalField(max_digits=10, decimal_places=2, required=False, initial=0)
