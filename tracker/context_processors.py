from django.conf import settings


def app_version(request):
    return {
        "APP_VERSION": getattr(settings, "APP_VERSION", "dev"),
        "GOOGLE_MAPS_KEY": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }
