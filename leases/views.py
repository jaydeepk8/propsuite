"""Lease CRUD views."""

from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)

from accounts.mixins import OwnerRequiredMixin
from .filters import LeaseFilter
from .forms import LeaseForm
from .models import Lease


class LeaseListView(OwnerRequiredMixin, ListView):
    """List leases visible to the current user, with search + status filter."""

    model = Lease
    template_name = "leases/lease_list.html"
    context_object_name = "leases"
    paginate_by = 10
    extra_context = {"active_nav": "leases"}

    def get_queryset(self):
        qs = (Lease.objects.for_user(self.request.user)
              .select_related("tenant__user", "unit__property"))
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(tenant__user__first_name__icontains=q)
                | Q(tenant__user__last_name__icontains=q)
                | Q(unit__unit_number__icontains=q)
                | Q(unit__property__title__icontains=q)
            )
        self.filterset = LeaseFilter(self.request.GET, queryset=qs)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter"] = self.filterset
        ctx["search_query"] = self.request.GET.get("q", "")
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class LeaseDetailView(OwnerRequiredMixin, DetailView):
    model = Lease
    template_name = "leases/lease_detail.html"
    context_object_name = "lease"
    extra_context = {"active_nav": "leases"}

    def get_queryset(self):
        return Lease.objects.for_user(self.request.user).select_related(
            "tenant__user", "unit__property"
        )


class LeaseFormMixin:
    """Shared config for create/update: inject the owner into the form."""

    model = Lease
    form_class = LeaseForm
    template_name = "leases/lease_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["owner"] = self.request.user
        return kwargs


class LeaseCreateView(OwnerRequiredMixin, LeaseFormMixin, CreateView):
    extra_context = {"active_nav": "leases", "form_title": "Create Lease"}

    def form_valid(self, form):
        messages.success(self.request, "Lease created. Unit status updated automatically.")
        return super().form_valid(form)


class LeaseUpdateView(OwnerRequiredMixin, LeaseFormMixin, UpdateView):
    extra_context = {"active_nav": "leases", "form_title": "Edit Lease"}

    def get_queryset(self):
        return Lease.objects.for_user(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Lease updated.")
        return super().form_valid(form)


class LeaseDeleteView(OwnerRequiredMixin, DeleteView):
    model = Lease
    template_name = "leases/lease_confirm_delete.html"
    success_url = reverse_lazy("leases:list")
    context_object_name = "lease"
    extra_context = {"active_nav": "leases"}

    def get_queryset(self):
        return Lease.objects.for_user(self.request.user).select_related(
            "tenant__user", "unit__property"
        )

    def form_valid(self, form):
        messages.success(self.request, "Lease deleted. Unit freed if no longer occupied.")
        return super().form_valid(form)
