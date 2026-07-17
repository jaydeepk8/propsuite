"""URL routes for leases."""

from django.urls import path

from . import views

app_name = "leases"

urlpatterns = [
    path("", views.LeaseListView.as_view(), name="list"),
    path("add/", views.LeaseCreateView.as_view(), name="create"),
    path("<int:pk>/", views.LeaseDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.LeaseUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.LeaseDeleteView.as_view(), name="delete"),
]
