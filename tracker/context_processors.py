from django.conf import settings


def app_version(request):
    return {
        "APP_VERSION": getattr(settings, "APP_VERSION", "dev"),
        "GOOGLE_MAPS_KEY": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }


def onbehalf_pending(request):
    """Count of reviews added on the current user's behalf that they haven't
    seen yet — drives the "reviews were added for you" banner. Cheap indexed
    counts; only runs for authenticated users."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {}
    from .models import ItemReview, LocationReview
    n = (
        LocationReview.objects.filter(user=user, submitted_by__isnull=False, subject_seen=False)
        .exclude(submitted_by=user).count()
        + ItemReview.objects.filter(user=user, submitted_by__isnull=False, subject_seen=False)
        .exclude(submitted_by=user).count()
    )
    return {"onbehalf_pending_count": n}
