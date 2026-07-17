"""Custom DRF permissions for the PropSuite API."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwnerOrAdmin(BasePermission):
    """Allow access only to property owners and administrators."""

    message = "Only property owners or administrators may perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_owner or user.is_admin))


class IsOwnerOrAdminOrReadOnly(BasePermission):
    """Any authenticated user may read; only owners/admins may write."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.is_owner or user.is_admin
