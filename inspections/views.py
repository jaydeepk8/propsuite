"""Inspection views."""

from django.contrib import messages
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)

from accounts.mixins import OwnerRequiredMixin
from .filters import InspectionFilter
from .forms import InspectionForm, InspectionReportForm
from .models import Inspection


class InspectionListView(OwnerRequiredMixin, ListView):
    """Inspection schedule with search, status filter and stat tiles."""

    model = Inspection
    template_name = "inspections/inspection_list.html"
    context_object_name = "inspections"
    paginate_by = 10
    extra_context = {"active_nav": "inspections"}

    def get_base_queryset(self):
        return (Inspection.objects.for_user(self.request.user)
                .select_related("property", "unit", "inspector"))

    def get_queryset(self):
        qs = self.get_base_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(property__title__icontains=q)
                | Q(unit__unit_number__icontains=q)
                | Q(notes__icontains=q)
            )
        self.filterset = InspectionFilter(self.request.GET, queryset=qs)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter"] = self.filterset
        ctx["search_query"] = self.request.GET.get("q", "")

        today = timezone.localdate()
        base = self.get_base_queryset()
        ctx["stats"] = base.aggregate(
            scheduled=Count("id", filter=Q(status=Inspection.Status.SCHEDULED,
                                           inspection_date__gte=today)),
            overdue=Count("id", filter=Q(status=Inspection.Status.SCHEDULED,
                                         inspection_date__lt=today)),
            completed=Count("id", filter=Q(status=Inspection.Status.COMPLETED)),
            reports=Count("id", filter=~Q(report="") & Q(report__isnull=False)),
        )
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class InspectionDetailView(OwnerRequiredMixin, DetailView):
    model = Inspection
    template_name = "inspections/inspection_detail.html"
    context_object_name = "inspection"
    extra_context = {"active_nav": "inspections"}

    def get_queryset(self):
        return (Inspection.objects.for_user(self.request.user)
                .select_related("property", "unit", "inspector"))


class InspectionFormMixin:
    model = Inspection
    form_class = InspectionForm
    template_name = "inspections/inspection_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["owner"] = self.request.user
        return kwargs


class InspectionCreateView(OwnerRequiredMixin, InspectionFormMixin, CreateView):
    extra_context = {"active_nav": "inspections", "form_title": "Schedule Inspection"}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Inspection scheduled.")
        return super().form_valid(form)


class InspectionUpdateView(OwnerRequiredMixin, InspectionFormMixin, UpdateView):
    extra_context = {"active_nav": "inspections", "form_title": "Edit Inspection"}

    def get_queryset(self):
        return Inspection.objects.for_user(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Inspection updated.")
        return super().form_valid(form)


class InspectionReportUploadView(OwnerRequiredMixin, UpdateView):
    """Attach the inspection report and mark the inspection Completed."""

    model = Inspection
    form_class = InspectionReportForm
    template_name = "inspections/inspection_report.html"
    context_object_name = "inspection"
    extra_context = {"active_nav": "inspections"}

    def get_queryset(self):
        return (Inspection.objects.for_user(self.request.user)
                .select_related("property", "unit"))

    def form_valid(self, form):
        # Uploading a report means the inspection has happened.
        form.instance.status = Inspection.Status.COMPLETED
        messages.success(self.request, "Report uploaded — inspection marked completed.")
        return super().form_valid(form)


class InspectionDeleteView(OwnerRequiredMixin, DeleteView):
    model = Inspection
    template_name = "inspections/inspection_confirm_delete.html"
    success_url = reverse_lazy("inspections:list")
    context_object_name = "inspection"
    extra_context = {"active_nav": "inspections"}

    def get_queryset(self):
        return (Inspection.objects.for_user(self.request.user)
                .select_related("property", "unit"))

    def form_valid(self, form):
        messages.success(self.request, "Inspection deleted.")
        return super().form_valid(form)
