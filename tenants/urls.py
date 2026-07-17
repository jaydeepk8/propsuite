"""URL routes for tenants."""

from django.urls import path

from . import views

app_name = "tenants"

urlpatterns = [
    path("", views.TenantListView.as_view(), name="list"),
    path("add/", views.TenantCreateView.as_view(), name="create"),
    path("<int:pk>/", views.TenantDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.TenantUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.TenantDeleteView.as_view(), name="delete"),
]
