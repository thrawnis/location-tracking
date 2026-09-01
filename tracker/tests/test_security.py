"""Security hardening from an earlier pass: CSV formula-injection escaping,
case-insensitive login, and rate limiting. Each of these was fixed once in
response to a specific finding and never had a regression test since.
"""
import csv
import io

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from tracker.forms import RegisterForm
from tracker.models import Location
from tracker.ratelimit import check_rate
from tracker.tests.helpers import TEST_PASSWORD, AppTestCase


class CsvFormulaInjectionTests(AppTestCase):
    """A location name/notes starting with =, +, -, @, tab, or CR can execute
    as a formula when the exported CSV is opened in Excel/Sheets. Each such
    cell must come back prefixed with a leading apostrophe."""

    def setUp(self):
        self.user = self.make_user("exporter")

    def _export_rows(self):
        self.login(self.user)
        resp = self.client.get(reverse("export_locations"))
        self.assertEqual(resp.status_code, 200)
        rows = list(csv.reader(io.StringIO(resp.content.decode())))
        return {row[0]: row for row in rows[1:]}   # name -> row, skip header

    def test_leading_equals_is_neutralised(self):
        Location.objects.create(name="=cmd|'/c calc'!A1", created_by=self.user)
        rows = self._export_rows()
        self.assertIn("'=cmd|'/c calc'!A1", rows)

    def test_leading_plus_minus_at_are_neutralised(self):
        Location.objects.create(name="+1 Diner", created_by=self.user)
        Location.objects.create(name="-Burger Place", created_by=self.user)
        Location.objects.create(name="@Cafe", created_by=self.user)
        rows = self._export_rows()
        self.assertIn("'+1 Diner", rows)
        self.assertIn("'-Burger Place", rows)
        self.assertIn("'@Cafe", rows)

    def test_ordinary_names_are_untouched(self):
        Location.objects.create(name="Ordinary Cafe", created_by=self.user)
        rows = self._export_rows()
        self.assertIn("Ordinary Cafe", rows)


class CaseInsensitiveLoginTests(TestCase):
    def test_login_succeeds_with_different_case_than_registered(self):
        User.objects.create_user(username="Alice", password=TEST_PASSWORD)
        ok = self.client.login(username="alice", password=TEST_PASSWORD)
        self.assertTrue(ok)

    def test_login_succeeds_with_all_caps(self):
        User.objects.create_user(username="Alice", password=TEST_PASSWORD)
        ok = self.client.login(username="ALICE", password=TEST_PASSWORD)
        self.assertTrue(ok)

    def test_wrong_password_still_fails(self):
        User.objects.create_user(username="Alice", password=TEST_PASSWORD)
        ok = self.client.login(username="alice", password="wrong password entirely")
        self.assertFalse(ok)

    def test_register_form_rejects_a_case_variant_of_an_existing_username(self):
        User.objects.create_user(username="Alice", password=TEST_PASSWORD)
        form = RegisterForm(data={
            "username": "alice", "email": "someone-else@example.com",
            "password1": "another-strong-pw-1", "password2": "another-strong-pw-1",
            "agree_terms": True, "captcha": "irrelevant",
        })
        form.is_valid()
        self.assertIn("username", form.errors)


class RateLimitTests(TestCase):
    """check_rate is a fixed-window counter shared across every @ratelimit
    endpoint — tested directly here since it's cheap and fast, plus one live
    endpoint (export, 10/hour) to prove the decorator actually enforces it."""

    def setUp(self):
        cache.clear()   # LocMemCache persists across test methods otherwise

    def test_allows_requests_within_the_limit(self):
        class FakeUser:
            is_authenticated = False
        request = type("R", (), {"META": {"REMOTE_ADDR": "10.0.0.1"}, "user": FakeUser()})()
        for _ in range(5):
            self.assertTrue(check_rate(request, "unit-test-bucket", 5, 60))

    def test_blocks_once_the_limit_is_exceeded(self):
        class FakeUser:
            is_authenticated = False
        request = type("R", (), {"META": {"REMOTE_ADDR": "10.0.0.2"}, "user": FakeUser()})()
        for _ in range(5):
            check_rate(request, "unit-test-bucket-2", 5, 60)
        self.assertFalse(check_rate(request, "unit-test-bucket-2", 5, 60))

    def test_different_clients_get_independent_counters(self):
        class FakeUser:
            is_authenticated = False

        def make_request(ip):
            return type("R", (), {"META": {"REMOTE_ADDR": ip}, "user": FakeUser()})()

        r1, r2 = make_request("10.0.0.3"), make_request("10.0.0.4")
        for _ in range(5):
            check_rate(r1, "unit-test-bucket-3", 5, 60)
        # r1 is now exhausted; r2 (different IP) must be unaffected.
        self.assertFalse(check_rate(r1, "unit-test-bucket-3", 5, 60))
        self.assertTrue(check_rate(r2, "unit-test-bucket-3", 5, 60))


class ExportRateLimitIntegrationTests(AppTestCase):
    def setUp(self):
        cache.clear()
        self.user = self.make_user("exporter2")
        self.login(self.user)

    def test_export_returns_429_after_ten_requests_in_an_hour(self):
        for _ in range(10):
            resp = self.client.get(reverse("export_locations"))
            self.assertEqual(resp.status_code, 200)
        resp = self.client.get(reverse("export_locations"))
        self.assertEqual(resp.status_code, 429)
