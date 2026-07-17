"""Notification views — every user sees only their own."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, View

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    """The user's notification inbox."""

    model = Notification
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20
    extra_context = {"active_nav": "notifications"}

    def get_queryset(self):
        qs = Notification.objects.for_user(self.request.user)
        if self.request.GET.get("filter") == "unread":
            qs = qs.unread()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["show_unread_only"] = self.request.GET.get("filter") == "unread"
        ctx["unread_total"] = Notification.objects.for_user(self.request.user).unread().count()
        return ctx


class NotificationReadView(LoginRequiredMixin, View):
    """Mark one notification read, then follow it to its target."""

    def get(self, request, pk, *args, **kwargs):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        notification.mark_read()
        return redirect(notification.url or reverse_lazy("notifications:list"))


class NotificationReadAllView(LoginRequiredMixin, View):
    """Mark every unread notification read."""

    def post(self, request, *args, **kwargs):
        count = Notification.objects.for_user(request.user).unread().update(is_read=True)
        messages.success(request, f"Marked {count} notification{'' if count == 1 else 's'} as read.")
        return redirect("notifications:list")
