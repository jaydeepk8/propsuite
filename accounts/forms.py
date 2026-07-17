"""Forms for authentication and profile management."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class EmailLoginForm(AuthenticationForm):
    """Login form that presents an 'email' label but accepts email or username."""

    username = forms.CharField(
        label="Email Address",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "name@company.com",
            "autofocus": True,
        }),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "••••••••",
        }),
    )


class RegisterForm(UserCreationForm):
    """
    Public self-registration. Users may register as a Property Owner or a
    Tenant only — Admin accounts are created by staff. Email is required and
    validated for uniqueness.
    """

    # Restrict selectable roles to Owner / Tenant.
    ROLE_CHOICES = [
        (User.Roles.OWNER, "Property Owner"),
        (User.Roles.TENANT, "Tenant"),
    ]
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        initial=User.Roles.TENANT,
    )

    class Meta:
        model = User
        fields = ("username", "email", "phone", "role", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "placeholder": "Choose a username"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@company.com"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "+91 98765 43210"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bootstrap-style the password fields UserCreationForm builds itself.
        self.fields["password1"].widget.attrs.update({"class": "form-control", "placeholder": "Create a password"})
        self.fields["password2"].widget.attrs.update({"class": "form-control", "placeholder": "Confirm password"})

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class ProfileForm(forms.ModelForm):
    """Edit basic profile details and profile image."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "profile_image")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "profile_image": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        # Uniqueness check excluding the current user.
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("That email is already in use.")
        return email
