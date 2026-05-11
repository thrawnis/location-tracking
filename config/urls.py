from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from tracker import views as tracker_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", tracker_views.login_view, name="login"),
    path("accounts/logout/", tracker_views.logout_view, name="logout"),
    path("accounts/register/", tracker_views.register_view, name="register"),
    path("", include("tracker.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
