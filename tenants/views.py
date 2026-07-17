"""Tenant CRUD views."""

from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)

from accounts.mixins import OwnerRequiredMixin
from .filters import TenantFilter
from .forms import TenantForm
from .models import Tenant


class TenantListView(OwnerRequiredMixin, ListView):
    """List of tenants visible to the current user, with search + filter."""

    model = Tenant
    template_name = "tenants/tenant_list.html"
    context_object_name = "tenants"
    paginate_by = 10
    extra_context = {"active_nav": "tenants"}

    def get_queryset(self):
        qs = Tenant.objects.for_user(self.request.user).select_related("user")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(user__first_name__icontains=q)
                | Q(user__last_name__icontains=q)
                | Q(user__email__icontains=q)
                | Q(occupation__icontains=q)
            )
        self.filterset = TenantFilter(self.request.GET, queryset=qs)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter"] = self.filterset
        ctx["search_query"] = self.request.GET.get("q", "")
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class TenantDetailView(OwnerRequiredMixin, DetailView):
    model = Tenant
    template_name = "tenants/tenant_detail.html"
    context_object_name = "tenant"
    extra_context = {"active_nav": "tenants"}

    def get_queryset(self):
        return Tenant.objects.for_user(self.request.user).select_related("user")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["leases"] = self.object.leases.select_related("unit__property").all()
        return ctx


class TenantFormMixin:
    """Shared config for create/update: inject the owner into the form."""

    model = Tenant
    form_class = TenantForm
    template_name = "tenants/tenant_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["owner"] = self.request.user
        return kwargs


class TenantCreateView(OwnerRequiredMixin, TenantFormMixin, CreateView):
    extra_context = {"active_nav": "tenants", "form_title": "Add Tenant"}

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Tenant added. They can set a password via “Forgot password”.",
        )
        return response


class TenantUpdateView(OwnerRequiredMixin, TenantFormMixin, UpdateView):
    extra_context = {"active_nav": "tenants", "form_title": "Edit Tenant"}

    def get_queryset(self):
        return Tenant.objects.for_user(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Tenant updated.")
        return super().form_valid(form)


class TenantDeleteView(OwnerRequiredMixin, DeleteView):
    model = Tenant
    template_name = "tenants/tenant_confirm_delete.html"
    success_url = reverse_lazy("tenants:list")
    context_object_name = "tenant"
    extra_context = {"active_nav": "tenants"}

    def get_queryset(self):
        return Tenant.objects.for_user(self.request.user).select_related("user")

    def form_valid(self, form):
        # Removing the linked user cascades to the tenant profile and leases.
        user = self.object.user
        messages.success(self.request, "Tenant removed.")
        response = super().form_valid(form)
        user.delete()
        return response
