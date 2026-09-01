"""Create (or reset) a Waypoint admin account without email verification.

Useful when SMTP isn't configured yet and you're locked out. Marks the
account as email-verified so the middleware won't gate it.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from tracker.models import EmailVerification, PendingRegistration


class Command(BaseCommand):
    help = "Create/reset an admin user and mark it email-verified."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True, help="Plain-text password (will be hashed).")

    def handle(self, *args, **opts):
        username = opts["username"].strip()
        email = opts["email"].strip()
        password = opts["password"]

        if not username or not email or not password:
            raise CommandError("username, email, and password are required")

        # Clear any stale pending signup for the same email/username.
        PendingRegistration.objects.filter(email__iexact=email).delete()
        PendingRegistration.objects.filter(username__iexact=username).delete()

        user, created = User.objects.get_or_create(
            username=username, defaults={"email": email},
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        EmailVerification.objects.update_or_create(
            user=user,
            defaults={"verified": True, "verified_at": timezone.now()},
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            "{} admin '{}' <{}> — email marked verified.".format(verb, username, email)
        ))
