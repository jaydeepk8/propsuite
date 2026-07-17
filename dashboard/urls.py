"""Dashboard and report URL routes."""

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardRedirectView.as_view(), name="redirect"),
    path("admin/", views.AdminDashboardView.as_view(), name="admin"),
    path("owner/", views.OwnerDashboardView.as_view(), name="owner"),
    path("tenant/", views.TenantDashboardView.as_view(), name="tenant"),

    # Analytics (bonus)
    path("analytics/", views.AnalyticsView.as_view(), name="analytics"),

    # Reports
    path("reports/", views.ReportIndexView.as_view(), name="reports"),
    path("reports/<slug:slug>/", views.ReportDetailView.as_view(), name="report_detail"),
]
