from django.urls import path

from . import views

urlpatterns = [
    # Two-factor authentication (TOTP)
    path("2fa/setup/", views.two_factor_setup, name="two_factor_setup"),
    path("2fa/verify/", views.two_factor_verify, name="two_factor_verify"),
    path("2fa/settings/", views.two_factor_settings, name="two_factor_settings"),
    path("2fa/disable/", views.two_factor_disable, name="two_factor_disable"),

    # Registration email confirmation (verify-first)
    path("register/confirm/", views.register_confirm, name="register_confirm"),

    # Email verification (for existing/legacy accounts)
    path("verify-email/", views.verify_email, name="verify_email"),
    path("verify-email/resend/", views.verify_email_resend, name="verify_email_resend"),
    path("verify-email/confirm/", views.verify_email_confirm, name="verify_email_confirm"),

    # Terms of Service
    path("terms/", views.terms, name="terms"),
    path("terms/accept/", views.terms_accept, name="terms_accept"),
    path("terms/decline/", views.terms_decline, name="terms_decline"),

    # Locations
    path("", views.location_list, name="location_list"),
    path("locations/new/", views.location_create, name="location_create"),
    path("locations/rate/", views.rate_poi, name="rate_poi"),
    path("locations/geojson/", views.locations_geojson, name="locations_geojson"),
    path("locations/<int:pk>/", views.location_detail, name="location_detail"),
    path("locations/<int:pk>/edit/", views.location_edit, name="location_edit"),
    path("locations/<int:pk>/delete/", views.location_delete, name="location_delete"),
    path("locations/<int:pk>/gf-vote/", views.gf_vote, name="gf_vote"),
    path("locations/<int:pk>/review/", views.location_review_upsert, name="location_review_upsert"),
    path("locations/<int:pk>/review/delete/", views.location_review_delete, name="location_review_delete"),

    # Collections
    path("collections/", views.collection_list, name="collection_list"),
    path("collections/<int:pk>/delete/", views.collection_delete, name="collection_delete"),
    path("collections/<int:pk>/toggle-public/", views.collection_toggle_public, name="collection_toggle_public"),
    path("collections/<int:pk>/toggle/<int:loc_pk>/", views.collection_toggle, name="collection_toggle"),

    # Public user profiles
    path("u/<str:username>/", views.user_profile, name="user_profile"),

    # Import / Export
    path("export/", views.export_locations, name="export_locations"),
    path("import/", views.import_locations, name="import_locations"),

    # Activity feed
    path("activity/", views.activity_feed, name="activity_feed"),

    # Duplicate detection
    path("api/locations/check-duplicate/", views.check_duplicate, name="check_duplicate"),

    # Items (HTMX)
    path("locations/<int:pk>/items/add/", views.item_add, name="item_add"),
    path("locations/<int:pk>/items/<int:item_pk>/edit/", views.item_edit, name="item_edit"),
    path("locations/<int:pk>/items/<int:item_pk>/delete/", views.item_delete, name="item_delete"),
    path("locations/<int:pk>/items/<int:item_pk>/review/", views.item_review_upsert, name="item_review_upsert"),
    path("locations/<int:pk>/items/<int:item_pk>/review/delete/", views.item_review_delete, name="item_review_delete"),

    # Photos (HTMX)
    path("locations/<int:pk>/photos/add/", views.photo_add, name="photo_add"),
    path("locations/<int:pk>/photos/<int:photo_pk>/delete/", views.photo_delete, name="photo_delete"),
    path("locations/<int:pk>/photos/<int:photo_pk>/rotate/", views.photo_rotate, name="photo_rotate"),

    # Admin (staff-only management)
    path("manage/", views.admin_dashboard, name="admin_dashboard"),
    path("manage/users/", views.admin_users, name="admin_users"),
    path("manage/users/<int:pk>/toggle-admin/", views.admin_user_toggle_admin, name="admin_user_toggle_admin"),
    path("manage/users/<int:pk>/toggle-superuser/", views.admin_user_toggle_superuser, name="admin_user_toggle_superuser"),
    path("manage/maps-usage/", views.maps_usage, name="maps_usage"),
    path("admin-log/", views.audit_log_view, name="audit_log"),

    # Server-side IP geolocation fallback
    path("api/geoip/", views.geoip_view, name="geoip"),

    # OSM POI search proxy (24-hour cache)
    path("api/osm/search/", views.osm_search, name="osm_search"),
]
