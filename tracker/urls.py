from django.urls import path

from . import views

urlpatterns = [
    # Locations
    path("", views.location_list, name="location_list"),
    path("locations/new/", views.location_create, name="location_create"),
    path("locations/geojson/", views.locations_geojson, name="locations_geojson"),
    path("locations/<int:pk>/", views.location_detail, name="location_detail"),
    path("locations/<int:pk>/edit/", views.location_edit, name="location_edit"),
    path("locations/<int:pk>/delete/", views.location_delete, name="location_delete"),

    # Items (HTMX)
    path("locations/<int:pk>/items/add/", views.item_add, name="item_add"),
    path("locations/<int:pk>/items/<int:item_pk>/edit/", views.item_edit, name="item_edit"),
    path("locations/<int:pk>/items/<int:item_pk>/delete/", views.item_delete, name="item_delete"),

    # Visits (HTMX)
    path("locations/<int:pk>/visits/add/", views.visit_add, name="visit_add"),
    path("locations/<int:pk>/visits/<int:visit_pk>/delete/", views.visit_delete, name="visit_delete"),

    # Photos (HTMX)
    path("locations/<int:pk>/photos/add/", views.photo_add, name="photo_add"),
    path("locations/<int:pk>/photos/<int:photo_pk>/delete/", views.photo_delete, name="photo_delete"),

    # Admin audit log
    path("admin-log/", views.audit_log_view, name="audit_log"),
]
