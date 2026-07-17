"""Role-based access decorators for function-based views."""

from functools import wraps

from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """
    Restrict a function-based view to the given roles.

    Usage::

        @role_required("OWNER", "ADMIN")
        def my_view(request): ...

    Admins always pass. Unauthenticated users are sent to login.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            if user.is_admin or user.role in roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped

    return decorator
