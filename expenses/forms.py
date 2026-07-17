"""Form for logging expenses."""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row
from django import forms

from properties.models import Property
from .models import Expense


class ExpenseForm(forms.ModelForm):
    """Log/edit an expense against one of the owner's properties."""

    class Meta:
        model = Expense
        fields = ("property", "category", "title", "amount", "date", "vendor", "notes")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner is not None:
            self.fields["property"].queryset = Property.objects.for_user(owner)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("property", css_class="col-md-6"),
                Column("category", css_class="col-md-6"),
            ),
            "title",
            Row(
                Column("amount", css_class="col-md-4"),
                Column("date", css_class="col-md-4"),
                Column("vendor", css_class="col-md-4"),
            ),
            "notes",
        )
