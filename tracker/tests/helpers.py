"""Shared test scaffolding.

Three onboarding gates sit in front of every authenticated view
(EmailVerificationMiddleware, TwoFactorMiddleware, TermsAcceptanceMiddleware —
see tracker/middleware.py) and have nothing to do with what most view tests
actually want to exercise. AppTestCase disables/satisfies all three up front
so a test can log a user in and go straight to the behaviour under test.
"""
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

from tracker.models import TermsAcceptance, TOTPDevice
from tracker.permissions import SUPERUSER_GROUP_NAME

TEST_PASSWORD = "correct horse battery staple 1"


def make_user(username, is_staff=False, superuser_role=False, password=TEST_PASSWORD):
    """A fully onboarded user: ToS accepted, 2FA satisfied if is_staff, and
    optionally in the app-level "Superuser" content-moderation group (distinct
    from Django's is_staff/is_superuser — see tracker/permissions.py)."""
    user = User.objects.create_user(
        username=username, password=password, email=f"{username}@example.com",
        is_staff=is_staff,
    )
    TermsAcceptance.objects.create(user=user, version=settings.TERMS_VERSION)
    if is_staff:
        TOTPDevice.objects.create(user=user, secret="JBSWY3DPEHPK3PXP", confirmed=True)
    if superuser_role:
        group, _ = Group.objects.get_or_create(name=SUPERUSER_GROUP_NAME)
        user.groups.add(group)
    return user


@override_settings(REQUIRE_EMAIL_VERIFICATION=False)
class AppTestCase(TestCase):
    """Base for view tests: the email-verification gate is disabled (ToS/2FA
    are satisfied per-user by make_user() instead, since there's no blanket
    settings switch for those)."""

    def make_user(self, username, **kwargs):
        return make_user(username, **kwargs)

    def login(self, user, password=TEST_PASSWORD):
        ok = self.client.login(username=user.username, password=password)
        assert ok, f"login() failed for {user.username} — wrong password?"
        return ok
