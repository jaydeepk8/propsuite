"""Model forms for properties and units."""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row, Submit
from django import forms

from .models import Property, Unit


class PropertyForm(forms.ModelForm):
    """Create/edit a property. Owner is assigned in the view, not here."""

    class Meta:
        model = Property
        fields = (
            "title", "property_type", "status", "description",
            "address", "city", "state", "country", "pincode",
            "total_units", "image",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False  # <form> is provided by the template
        self.helper.layout = Layout(
            Row(
                Column("title", css_class="col-md-8"),
                Column("property_type", css_class="col-md-4"),
            ),
            Row(
                Column("status", css_class="col-md-4"),
                Column("total_units", css_class="col-md-4"),
                Column("pincode", css_class="col-md-4"),
            ),
            "description",
            "address",
            Row(
                Column("city", css_class="col-md-4"),
                Column("state", css_class="col-md-4"),
                Column("country", css_class="col-md-4"),
            ),
            "image",
        )


class UnitForm(forms.ModelForm):
    """Create/edit a single unit within a property."""

    class Meta:
        model = Unit
        fields = (
            "unit_number", "floor", "bedrooms", "bathrooms",
            "rent_amount", "security_deposit", "status",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("unit_number", css_class="col-md-6"),
                Column("floor", css_class="col-md-6"),
            ),
            Row(
                Column("bedrooms", css_class="col-md-6"),
                Column("bathrooms", css_class="col-md-6"),
            ),
            Row(
                Column("rent_amount", css_class="col-md-6"),
                Column("security_deposit", css_class="col-md-6"),
            ),
            "status",
        )
