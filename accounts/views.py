"""Authentication and profile views."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView

from .forms import EmailLoginForm, ProfileForm, RegisterForm
from .models import User


class PropSuiteLoginView(LoginView):
    """Email/username + password login using the split-screen auth shell."""

    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True


class PropSuiteLogoutView(LogoutView):
    """Log the user out (POST) and return to the login page."""

    next_page = reverse_lazy("accounts:login")


class RegisterView(CreateView):
    """Public self-registration; logs the user in on success."""

    model = User
    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("dashboard:redirect")

    def form_valid(self, form):
        response = super().form_valid(form)
        # Authenticate the new user against our email/username backend.
        login(self.request, self.object,
              backend="accounts.backends.EmailOrUsernameBackend")
        messages.success(self.request, "Welcome to PropSuite! Your account is ready.")
        return response


class ProfileView(LoginRequiredMixin, UpdateView):
    """View and edit the signed-in user's own profile."""

    model = User
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        # Always operate on the current user — never another account.
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Your profile has been updated.")
        return super().form_valid(form)
