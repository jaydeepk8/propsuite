"""
Notification helpers.

Everything that creates a notification goes through `notify()` so the rules
(skip missing users, optional email) live in exactly one place.
"""

from django.conf import settings
from django.core.mail import send_mail

from .models import Notification


def notify(user, title, message="", kind=Notification.Kind.GENERAL, url="", email=False):
    """
    Create an in-app notification for `user`.

    Returns the Notification, or None when there's no user to notify (e.g. an
    unassigned request), which keeps the signal receivers simple.
    """
    if user is None:
        return None

    notification = Notification.objects.create(
        user=user, title=title, message=message, kind=kind, url=url or "",
    )

    if email and user.email:
        # Failures must never break the request that triggered the notice.
        send_mail(
            subject=title,
            message=message or title,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

    return notification


def notify_many(users, *args, **kwargs):
    """Notify several users, skipping duplicates and Nones."""
    seen = set()
    created = []
    for user in users:
        if user is None or user.pk in seen:
            continue
        seen.add(user.pk)
        result = notify(user, *args, **kwargs)
        if result:
            created.append(result)
    return created
