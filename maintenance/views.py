"""Maintenance request views.

Unlike the other modules, maintenance is used by *both* roles: tenants raise
requests, owners assign them and drive the status forward. Access is scoped
by `MaintenanceQuerySet.for_user`.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)

from accounts.mixins import OwnerRequiredMixin
from leases.models import Lease
from .filters import MaintenanceFilter
from .forms import MaintenanceManageForm, MaintenanceRequestForm
from .models import MaintenanceRequest


class MaintenanceListView(LoginRequiredMixin, ListView):
    """Ticket list — scoped to the user's role, with search and filters."""

    model = MaintenanceRequest
    template_name = "maintenance/maintenance_list.html"
    context_object_name = "requests"
    paginate_by = 10
    extra_context = {"active_nav": "maintenance"}

    def get_base_queryset(self):
        return (MaintenanceRequest.objects.for_user(self.request.user)
                .select_related("unit__property", "tenant__user", "assigned_to"))

    def get_queryset(self):
        qs = self.get_base_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(unit__unit_number__icontains=q)
                | Q(unit__property__title__icontains=q)
            )
        self.filterset = MaintenanceFilter(self.request.GET, queryset=qs)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter"] = self.filterset
        ctx["search_query"] = self.request.GET.get("q", "")

        base = self.get_base_queryset()
        agg = base.aggregate(
            open_count=Count("id", filter=~Q(status=MaintenanceRequest.Status.COMPLETED)),
            high=Count("id", filter=Q(priority=MaintenanceRequest.Priority.HIGH)
                       & ~Q(status=MaintenanceRequest.Status.COMPLETED)),
            in_progress=Count("id", filter=Q(status=MaintenanceRequest.Status.IN_PROGRESS)),
            completed=Count("id", filter=Q(status=MaintenanceRequest.Status.COMPLETED)),
        )
        ctx["stats"] = agg
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class MaintenanceDetailView(LoginRequiredMixin, DetailView):
    model = MaintenanceRequest
    template_name = "maintenance/maintenance_detail.html"
    context_object_name = "request_obj"
    extra_context = {"active_nav": "maintenance"}

    def get_queryset(self):
        return (MaintenanceRequest.objects.for_user(self.request.user)
                .select_related("unit__property", "tenant__user", "assigned_to"))


class MaintenanceCreateView(LoginRequiredMixin, CreateView):
    """Raise a request. Tenants pick from units they lease."""

    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = "maintenance/maintenance_form.html"
    extra_context = {"active_nav": "maintenance", "form_title": "New Maintenance Request"}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        form.instance.created_by = user

        if user.is_tenant:
            form.instance.tenant = getattr(user, "tenant_profile", None)
        else:
            # Owner/admin raising a ticket: attribute it to the unit's
            # current tenant, if the unit is leased.
            active = (Lease.objects.filter(unit=form.instance.unit,
                                           status=Lease.Status.ACTIVE)
                      .select_related("tenant").first())
            form.instance.tenant = active.tenant if active else None

        messages.success(self.request, "Maintenance request submitted.")
        return super().form_valid(form)


class MaintenanceUpdateView(LoginRequiredMixin, UpdateView):
    """Edit the core details of a request."""

    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = "maintenance/maintenance_form.html"
    extra_context = {"active_nav": "maintenance", "form_title": "Edit Request"}

    def get_queryset(self):
        return MaintenanceRequest.objects.for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Request updated.")
        return super().form_valid(form)


class MaintenanceManageView(OwnerRequiredMixin, UpdateView):
    """Owner/admin: assign the request and move its status forward."""

    model = MaintenanceRequest
    form_class = MaintenanceManageForm
    template_name = "maintenance/maintenance_manage.html"
    context_object_name = "request_obj"
    extra_context = {"active_nav": "maintenance"}

    def get_queryset(self):
        return (MaintenanceRequest.objects.for_user(self.request.user)
                .select_related("unit__property", "tenant__user"))

    def form_valid(self, form):
        # Assigning someone while still Open implies the ticket is assigned.
        if (form.cleaned_data.get("assigned_to")
                and form.instance.status == MaintenanceRequest.Status.OPEN):
            form.instance.status = MaintenanceRequest.Status.ASSIGNED
        messages.success(self.request, "Request updated.")
        return super().form_valid(form)


class MaintenanceDeleteView(LoginRequiredMixin, DeleteView):
    model = MaintenanceRequest
    template_name = "maintenance/maintenance_confirm_delete.html"
    success_url = reverse_lazy("maintenance:list")
    context_object_name = "request_obj"
    extra_context = {"active_nav": "maintenance"}

    def get_queryset(self):
        return MaintenanceRequest.objects.for_user(self.request.user).select_related(
            "unit__property")

    def form_valid(self, form):
        messages.success(self.request, "Request deleted.")
        return super().form_valid(form)
