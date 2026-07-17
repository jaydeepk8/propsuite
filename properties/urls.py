"""URL routes for properties and units."""

from django.urls import path

from . import views

app_name = "properties"

urlpatterns = [
    # Properties
    path("", views.PropertyListView.as_view(), name="list"),
    path("add/", views.PropertyCreateView.as_view(), name="create"),
    path("<int:pk>/", views.PropertyDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.PropertyUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.PropertyDeleteView.as_view(), name="delete"),

    # Units
    path("units/", views.UnitListView.as_view(), name="unit_list"),
    path("<int:property_pk>/units/add/", views.UnitCreateView.as_view(), name="unit_create"),
    path("units/<int:pk>/edit/", views.UnitUpdateView.as_view(), name="unit_update"),
    path("units/<int:pk>/delete/", views.UnitDeleteView.as_view(), name="unit_delete"),
]
