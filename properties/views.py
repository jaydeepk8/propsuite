"""Property and Unit views (class-based)."""

from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)

from accounts.mixins import OwnerRequiredMixin
from .filters import PropertyFilter, UnitFilter
from .forms import PropertyForm, UnitForm
from .models import Property, Unit


class OwnedPropertyMixin(OwnerRequiredMixin):
    """
    For edit/delete views: restrict the queryset to properties the current
    user owns (admins may touch any). Prevents owners editing each other's
    properties even by guessing a URL.
    """

    def get_queryset(self):
        return Property.objects.for_user(self.request.user)


# ── Property CRUD ───────────────────────────────────────
class PropertyListView(OwnerRequiredMixin, ListView):
    """Card grid of properties with search, filtering and pagination."""

    model = Property
    template_name = "properties/property_list.html"
    context_object_name = "properties"
    paginate_by = 6
    extra_context = {"active_nav": "properties"}

    def get_base_queryset(self):
        """All properties visible to this user (before search/filter)."""
        return Property.objects.for_user(self.request.user).with_owner()

    def get_queryset(self):
        qs = self.get_base_queryset()

        # Free-text search across title / city / address.
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(city__icontains=q)
                | Q(address__icontains=q)
            )

        # django-filter (city / type / status).
        self.filterset = PropertyFilter(self.request.GET, queryset=qs)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter"] = self.filterset
        ctx["search_query"] = self.request.GET.get("q", "")

        # Portfolio stat tiles — computed across the user's whole portfolio.
        units = Unit.objects.filter(property__in=self.get_base_queryset())
        agg = units.aggregate(
            total=Count("id"),
            occupied=Count("id", filter=Q(status=Unit.Status.OCCUPIED)),
            income=Sum("rent_amount", filter=Q(status=Unit.Status.OCCUPIED)),
        )
        total = agg["total"] or 0
        occupied = agg["occupied"] or 0

        # Imported here (not at module level) to avoid a circular import:
        # the maintenance app depends on properties.
        from maintenance.models import MaintenanceRequest

        open_tickets = MaintenanceRequest.objects.filter(unit__in=units).open()
        ctx["stats"] = {
            "total_units": total,
            "occupancy_rate": round((occupied / total) * 100, 1) if total else 0.0,
            "gross_income": agg["income"] or Decimal("0.00"),
            "open_tickets": open_tickets.count(),
            "high_priority_tickets": open_tickets.filter(
                priority=MaintenanceRequest.Priority.HIGH
            ).count(),
        }
        # Preserve non-page query params for pagination links.
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class PropertyDetailView(OwnerRequiredMixin, DetailView):
    """Property overview with its units."""

    model = Property
    template_name = "properties/property_detail.html"
    context_object_name = "property"
    extra_context = {"active_nav": "properties"}

    def get_queryset(self):
        return Property.objects.for_user(self.request.user).with_owner()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["units"] = self.object.units.all()
        return ctx


class PropertyCreateView(OwnerRequiredMixin, CreateView):
    """Add a new property owned by the current user."""

    model = Property
    form_class = PropertyForm
    template_name = "properties/property_form.html"
    extra_context = {"active_nav": "properties", "form_title": "Add Property"}

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Property created successfully.")
        return super().form_valid(form)


class PropertyUpdateView(OwnedPropertyMixin, UpdateView):
    """Edit an existing property (owner/admin only)."""

    model = Property
    form_class = PropertyForm
    template_name = "properties/property_form.html"
    extra_context = {"active_nav": "properties", "form_title": "Edit Property"}

    def form_valid(self, form):
        messages.success(self.request, "Property updated successfully.")
        return super().form_valid(form)


class PropertyDeleteView(OwnedPropertyMixin, DeleteView):
    """Delete a property (owner/admin only)."""

    model = Property
    template_name = "properties/property_confirm_delete.html"
    success_url = reverse_lazy("properties:list")
    extra_context = {"active_nav": "properties"}

    def form_valid(self, form):
        messages.success(self.request, "Property deleted.")
        return super().form_valid(form)


# ── Units ───────────────────────────────────────────────
class UnitListView(OwnerRequiredMixin, ListView):
    """All units across the user's properties, with status filtering."""

    model = Unit
    template_name = "properties/unit_list.html"
    context_object_name = "units"
    paginate_by = 12
    extra_context = {"active_nav": "units"}

    def get_queryset(self):
        qs = (Unit.objects
              .filter(property__in=Property.objects.for_user(self.request.user))
              .select_related("property"))
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(unit_number__icontains=q) | Q(property__title__icontains=q)
            )
        self.filterset = UnitFilter(self.request.GET, queryset=qs)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter"] = self.filterset
        ctx["search_query"] = self.request.GET.get("q", "")
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class UnitOwnerMixin(OwnerRequiredMixin):
    """Resolve the parent property and enforce ownership for unit edits."""

    def get_property(self):
        return get_object_or_404(
            Property.objects.for_user(self.request.user),
            pk=self.kwargs["property_pk"],
        )


class UnitCreateView(UnitOwnerMixin, CreateView):
    """Add a unit to a specific property."""

    model = Unit
    form_class = UnitForm
    template_name = "properties/unit_form.html"
    extra_context = {"active_nav": "units", "form_title": "Add Unit"}

    def dispatch(self, request, *args, **kwargs):
        self.property = self.get_property()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.property = self.property
        messages.success(self.request, "Unit added.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["property"] = self.property
        return ctx

    def get_success_url(self):
        return reverse("properties:detail", kwargs={"pk": self.property.pk})


class UnitUpdateView(OwnerRequiredMixin, UpdateView):
    """Edit a unit (must belong to a property the user owns)."""

    model = Unit
    form_class = UnitForm
    template_name = "properties/unit_form.html"
    extra_context = {"active_nav": "units", "form_title": "Edit Unit"}

    def get_queryset(self):
        return Unit.objects.filter(
            property__in=Property.objects.for_user(self.request.user)
        ).select_related("property")

    def form_valid(self, form):
        messages.success(self.request, "Unit updated.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["property"] = self.object.property
        return ctx

    def get_success_url(self):
        return reverse("properties:detail", kwargs={"pk": self.object.property_id})


class UnitDeleteView(OwnerRequiredMixin, DeleteView):
    """Delete a unit (owner/admin only)."""

    model = Unit
    template_name = "properties/unit_confirm_delete.html"
    extra_context = {"active_nav": "units"}

    def get_queryset(self):
        return Unit.objects.filter(
            property__in=Property.objects.for_user(self.request.user)
        ).select_related("property")

    def form_valid(self, form):
        messages.success(self.request, "Unit deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("properties:detail", kwargs={"pk": self.object.property_id})
