"""
Dashboard views.

`DashboardRedirectView` is the post-login landing point: it inspects the
user's role and forwards to the matching dashboard. Each dashboard pulls its
numbers from `dashboard.selectors`, keeping these views thin.
"""

import calendar

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from django.views.generic import RedirectView, TemplateView

from accounts.mixins import AdminRequiredMixin, OwnerRequiredMixin, TenantRequiredMixin
from properties.models import Property
from . import selectors
from .exporters import render_csv, render_pdf
from .reports import REPORTS


class DashboardRedirectView(LoginRequiredMixin, RedirectView):
    """Route each user to their role-specific dashboard after login."""

    def get_redirect_url(self, *args, **kwargs):
        user = self.request.user
        if user.is_admin:
            return reverse("dashboard:admin")
        if user.is_owner:
            return reverse("dashboard:owner")
        return reverse("dashboard:tenant")


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    template_name = "dashboard/admin_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "dashboard"
        ctx.update(selectors.admin_dashboard(self.request.user))
        return ctx


class OwnerDashboardView(OwnerRequiredMixin, TemplateView):
    template_name = "dashboard/owner_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "dashboard"
        ctx.update(selectors.owner_dashboard(self.request.user))
        return ctx


class TenantDashboardView(TenantRequiredMixin, TemplateView):
    template_name = "dashboard/tenant_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "dashboard"
        ctx.update(selectors.tenant_dashboard(self.request.user))
        return ctx


class AnalyticsView(OwnerRequiredMixin, TemplateView):
    """Occupancy and income-vs-expense analytics (bonus feature)."""

    template_name = "dashboard/analytics.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "analytics"
        ctx.update(selectors.occupancy_analytics(self.request.user))
        return ctx


# ── Reports ─────────────────────────────────────────────
class ReportIndexView(OwnerRequiredMixin, TemplateView):
    """Hub listing every available report."""

    template_name = "dashboard/report_index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "reports"
        ctx["reports"] = REPORTS.values()
        return ctx


class ReportDetailView(OwnerRequiredMixin, TemplateView):
    """
    Render one report: HTML preview by default, or a CSV/PDF download when
    `?format=csv|pdf` is supplied.
    """

    template_name = "dashboard/report_detail.html"

    def get_report(self):
        # Cached: get() and get_context_data() both need it, and building
        # rows twice would double every query.
        if not hasattr(self, "_report"):
            report_class = REPORTS.get(self.kwargs["slug"])
            if report_class is None:
                raise Http404("Unknown report.")
            self._report = report_class(self.request.user, self.request.GET)
        return self._report

    def get(self, request, *args, **kwargs):
        report = self.get_report()
        export = request.GET.get("format")
        if export == "csv":
            return render_csv(report)
        if export == "pdf":
            return render_pdf(report)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        report = self.get_report()
        today = timezone.localdate()
        ctx.update({
            "active_nav": "reports",
            "report": report,
            "summary": report.summary(),
            "total_row": report.total_row(),
            "properties": Property.objects.for_user(self.request.user),
            "months": [(i, calendar.month_name[i]) for i in range(1, 13)],
            "years": range(today.year, today.year - 5, -1),
            # Preserve the current filters on the export links.
            "export_qs": self.request.GET.urlencode(),
        })
        return ctx
