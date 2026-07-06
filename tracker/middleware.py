from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class EmailVerificationMiddleware:
    """Require every authenticated user to confirm their email before using the
    app. Redirects unverified users to the verification page. Disabled when
    settings.REQUIRE_EMAIL_VERIFICATION is False."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "REQUIRE_EMAIL_VERIFICATION", True):
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated:
                if not request.session.get("email_verified") and not self._is_exempt(request):
                    from .models import EmailVerification
                    ev = EmailVerification.objects.filter(user=user).first()
                    if ev and ev.verified:
                        request.session["email_verified"] = True
                    else:
                        return redirect("verify_email")
        return self.get_response(request)

    def _is_exempt(self, request):
        path = request.path
        for name in ("verify_email", "verify_email_confirm", "verify_email_resend", "logout"):
            try:
                if path == reverse(name):
                    return True
            except Exception:
                pass
        return (
            path.startswith(settings.STATIC_URL)
            or path.startswith(getattr(settings, "MEDIA_URL", "/media/"))
        )


class TermsAcceptanceMiddleware:
    """Require every authenticated user to accept the current Terms of Service.

    Users who have never accepted, or who accepted an older version (after the
    terms change and TERMS_VERSION is bumped), are redirected to the terms page
    and cannot use the rest of the app until they accept.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            current = settings.TERMS_VERSION
            # Fast path: the session already confirms the current version, so
            # accepted users skip the exempt-path checks and the DB query.
            if request.session.get("tos_accepted_version") != current and not self._is_exempt(request):
                from .models import TermsAcceptance
                if TermsAcceptance.objects.filter(user=user, version=current).exists():
                    request.session["tos_accepted_version"] = current
                else:
                    return redirect("{}?next={}".format(reverse("terms"), request.path))
        return self.get_response(request)

    def _is_exempt(self, request):
        path = request.path
        # The terms flow, the email-verification flow (which must complete
        # first), logout, and static assets must stay reachable.
        exempt_names = (
            "terms", "terms_accept", "terms_decline", "logout",
            "verify_email", "verify_email_resend", "verify_email_confirm",
        )
        for name in exempt_names:
            try:
                if path == reverse(name):
                    return True
            except Exception:
                pass
        return (
            path.startswith(settings.STATIC_URL)
            or path.startswith(getattr(settings, "MEDIA_URL", "/media/"))
        )
