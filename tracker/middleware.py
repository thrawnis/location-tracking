from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


# URL names that every gate must leave reachable, so one gate never blocks
# another gate's remediation page (order of middlewares then just decides which
# gate a user is sent to first).
_GATE_EXEMPT_NAMES = (
    "logout",
    "verify_email", "verify_email_resend", "verify_email_confirm", "register_confirm",
    "two_factor_setup", "two_factor_verify", "two_factor_disable", "two_factor_settings",
    "terms", "terms_accept", "terms_decline",
)


def _is_gate_exempt(request):
    path = request.path
    for name in _GATE_EXEMPT_NAMES:
        try:
            if path == reverse(name):
                return True
        except Exception:
            pass
    return (
        path.startswith(settings.STATIC_URL)
        or path.startswith(getattr(settings, "MEDIA_URL", "/media/"))
    )


class EmailVerificationMiddleware:
    """Require every authenticated user to confirm their email before using the
    app. Disabled when settings.REQUIRE_EMAIL_VERIFICATION is False."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "REQUIRE_EMAIL_VERIFICATION", True):
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated:
                if not request.session.get("email_verified") and not _is_gate_exempt(request):
                    from .models import EmailVerification
                    ev = EmailVerification.objects.filter(user=user).first()
                    if ev and ev.verified:
                        request.session["email_verified"] = True
                    else:
                        return redirect("verify_email")
        return self.get_response(request)


class TwoFactorMiddleware:
    """Admins must have two-factor authentication enabled. Any signed-in admin
    without a confirmed TOTP device is redirected to the setup page until they
    finish. Optional (unenforced) for non-admin users."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.is_staff:
            if not request.session.get("twofa_ok") and not _is_gate_exempt(request):
                from .models import TOTPDevice
                if TOTPDevice.objects.filter(user=user, confirmed=True).exists():
                    request.session["twofa_ok"] = True
                else:
                    return redirect("two_factor_setup")
        return self.get_response(request)


class TermsAcceptanceMiddleware:
    """Require every authenticated user to accept the current Terms of Service.
    Bumping TERMS_VERSION forces everyone to re-accept."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            current = settings.TERMS_VERSION
            if request.session.get("tos_accepted_version") != current and not _is_gate_exempt(request):
                from .models import TermsAcceptance
                if TermsAcceptance.objects.filter(user=user, version=current).exists():
                    request.session["tos_accepted_version"] = current
                else:
                    return redirect("{}?next={}".format(reverse("terms"), request.path))
        return self.get_response(request)
