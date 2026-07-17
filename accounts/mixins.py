"""Reusable role-based access mixins for class-based views."""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Base mixin: require login AND one of `allowed_roles`.

    Set `allowed_roles` on the view, e.g.::

        class OwnerOnlyView(RoleRequiredMixin, ListView):
            allowed_roles = ["OWNER"]
    """

    allowed_roles: list[str] = []

    def test_func(self):
        user = self.request.user
        # Superusers/admins always pass.
        if user.is_admin:
            return True
        return user.role in self.allowed_roles


class AdminRequiredMixin(RoleRequiredMixin):
    """Restrict a view to platform administrators."""

    allowed_roles = ["ADMIN"]


class OwnerRequiredMixin(RoleRequiredMixin):
    """Restrict a view to property owners (admins allowed too)."""

    allowed_roles = ["OWNER"]


class TenantRequiredMixin(RoleRequiredMixin):
    """Restrict a view to tenants (admins allowed too)."""

    allowed_roles = ["TENANT"]
