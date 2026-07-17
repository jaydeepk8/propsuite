"""Template context processors for the notifications app."""


def unread_notifications(request):
    """
    Expose the current user's unread-notification count to every template.

    Returns 0 for anonymous users so the navbar badge renders safely on
    public pages. Also degrades gracefully before the Notification model
    exists (the reverse `notifications` relation is added in that milestone).
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"unread_notification_count": 0}

    related = getattr(user, "notifications", None)
    if related is None:
        return {"unread_notification_count": 0}

    return {"unread_notification_count": related.filter(is_read=False).count()}
