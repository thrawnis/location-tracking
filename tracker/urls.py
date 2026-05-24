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
    path("locations/<int:pk>/items/<int:item_pk>/review/", views.item_review_upsert, name="item_review_upsert"),
    path("locations/<int:pk>/items/<int:item_pk>/review/delete/", views.item_review_delete, name="item_review_delete"),

    # Visits (HTMX)
    path("locations/<int:pk>/visits/add/", views.visit_add, name="visit_add"),
    path("locations/<int:pk>/visits/<int:visit_pk>/delete/", views.visit_delete, name="visit_delete"),

    # Photos (HTMX)
    path("locations/<int:pk>/photos/add/", views.photo_add, name="photo_add"),
    path("locations/<int:pk>/photos/<int:photo_pk>/delete/", views.photo_delete, name="photo_delete"),
    path("locations/<int:pk>/photos/<int:photo_pk>/rotate/", views.photo_rotate, name="photo_rotate"),

    # Admin audit log
    path("admin-log/", views.audit_log_view, name="audit_log"),

    # Server-side IP geolocation fallback
    path("api/geoip/", views.geoip_view, name="geoip"),

    # OSM POI search proxy (24-hour cache)
    path("api/osm/search/", views.osm_search, name="osm_search"),
]
