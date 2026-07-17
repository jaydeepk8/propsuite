"""Forms for scheduling inspections and uploading reports."""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row
from django import forms
from django.contrib.auth import get_user_model

from properties.models import Property, Unit
from .models import Inspection

User = get_user_model()


class InspectionForm(forms.ModelForm):
    """Schedule or edit an inspection. Choices are scoped to the owner."""

    class Meta:
        model = Inspection
        fields = ("property", "unit", "inspector", "inspection_date",
                  "status", "notes", "report")
        widgets = {
            "inspection_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)

        if owner is not None:
            props = Property.objects.for_user(owner)
            self.fields["property"].queryset = props
            self.fields["unit"].queryset = (
                Unit.objects.filter(property__in=props).select_related("property")
            )
            self.fields["inspector"].queryset = User.objects.filter(
                role__in=[User.Roles.OWNER, User.Roles.ADMIN]
            )

        self.fields["unit"].required = False
        self.fields["unit"].help_text = "Leave blank to inspect the whole property."
        self.fields["inspector"].required = False

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("property", css_class="col-md-6"),
                Column("unit", css_class="col-md-6"),
            ),
            Row(
                Column("inspector", css_class="col-md-4"),
                Column("inspection_date", css_class="col-md-4"),
                Column("status", css_class="col-md-4"),
            ),
            "notes",
            "report",
        )

    def clean(self):
        cleaned = super().clean()
        unit, prop = cleaned.get("unit"), cleaned.get("property")
        # Mirror the model rule at form level for a friendly message.
        if unit and prop and unit.property_id != prop.pk:
            self.add_error("unit", "That unit doesn't belong to the selected property.")
        return cleaned


class InspectionReportForm(forms.ModelForm):
    """Focused form for the "upload report" action — marks it Completed."""

    class Meta:
        model = Inspection
        fields = ("report", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 4, "class": "form-control"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["report"].required = True
        self.fields["report"].widget.attrs.update({"class": "form-control"})
