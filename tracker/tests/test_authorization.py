"""Authorization boundaries: who may edit/delete what.

Every one of these views has a hand-written permission check (creator-or-
superuser, uploader-or-superuser, owner-or-superuser, membership...) with no
test previously enforcing it. These pin the actual contract: the wrong user
gets 403 (or 404 where the view intentionally hides the object rather than
confirming it exists), the right user succeeds, and a superuser-role/admin
override always works regardless of ownership.
"""
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from tracker.models import ChainGroup, Collection, FriendGroup, FriendGroupMembership, Item, Location, Photo
from tracker.tests.helpers import AppTestCase

# The smallest possible valid PNG (1x1, transparent) — real enough for
# Photo.save()'s Pillow-based resize step to open without error.
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def make_location(owner, name="Test Cafe", **extra):
    return Location.objects.create(name=name, created_by=owner, **extra)


class LocationEditDeleteTests(AppTestCase):
    def setUp(self):
        self.owner = self.make_user("owner")
        self.other = self.make_user("other")
        self.superuser_role = self.make_user("mod", superuser_role=True)
        self.admin = self.make_user("admin", is_staff=True)
        self.loc = make_location(self.owner)

    def test_edit_forbidden_for_unrelated_user(self):
        self.login(self.other)
        resp = self.client.post(
            reverse("location_edit", args=[self.loc.pk]),
            {"name": "Hijacked Name"},
        )
        self.assertEqual(resp.status_code, 403)
        self.loc.refresh_from_db()
        self.assertEqual(self.loc.name, "Test Cafe")

    def test_edit_allowed_for_creator(self):
        self.login(self.owner)
        resp = self.client.post(
            reverse("location_edit", args=[self.loc.pk]),
            {"name": "Renamed by owner", "gluten_free": "", "dietary_notes": "",
             "public_notes": "", "private_notes": "", "google_place_id": "",
             "address": "", "city": "", "state": "", "latitude": "", "longitude": ""},
        )
        self.assertEqual(resp.status_code, 302)
        self.loc.refresh_from_db()
        self.assertEqual(self.loc.name, "Renamed by owner")

    def test_edit_allowed_for_superuser_role(self):
        self.login(self.superuser_role)
        resp = self.client.post(
            reverse("location_edit", args=[self.loc.pk]),
            {"name": "Renamed by mod", "gluten_free": "", "dietary_notes": "",
             "public_notes": "", "private_notes": "", "google_place_id": "",
             "address": "", "city": "", "state": "", "latitude": "", "longitude": ""},
        )
        self.assertEqual(resp.status_code, 302)
        self.loc.refresh_from_db()
        self.assertEqual(self.loc.name, "Renamed by mod")

    def test_edit_allowed_for_admin(self):
        self.login(self.admin)
        resp = self.client.post(
            reverse("location_edit", args=[self.loc.pk]),
            {"name": "Renamed by admin", "gluten_free": "", "dietary_notes": "",
             "public_notes": "", "private_notes": "", "google_place_id": "",
             "address": "", "city": "", "state": "", "latitude": "", "longitude": ""},
        )
        self.assertEqual(resp.status_code, 302)
        self.loc.refresh_from_db()
        self.assertEqual(self.loc.name, "Renamed by admin")

    def test_delete_forbidden_for_unrelated_user(self):
        self.login(self.other)
        resp = self.client.post(
            reverse("location_delete", args=[self.loc.pk]), {"reason": "spam"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Location.objects.filter(pk=self.loc.pk).exists())

    def test_delete_allowed_for_creator(self):
        self.login(self.owner)
        resp = self.client.post(
            reverse("location_delete", args=[self.loc.pk]), {"reason": "no longer exists"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Location.objects.filter(pk=self.loc.pk).exists())

    def test_delete_allowed_for_superuser_role(self):
        self.login(self.superuser_role)
        resp = self.client.post(
            reverse("location_delete", args=[self.loc.pk]), {"reason": "duplicate"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Location.objects.filter(pk=self.loc.pk).exists())


class LocationChainLinkTests(AppTestCase):
    def setUp(self):
        self.owner = self.make_user("owner")
        self.other = self.make_user("other")
        self.superuser_role = self.make_user("mod", superuser_role=True)
        self.loc_a = make_location(self.owner, name="Burger King A")
        self.loc_b = make_location(self.owner, name="Burger King B")

    def test_link_forbidden_without_edit_rights_on_source(self):
        self.login(self.other)
        resp = self.client.post(
            reverse("location_link", args=[self.loc_a.pk, self.loc_b.pk]),
        )
        self.assertEqual(resp.status_code, 403)
        self.loc_a.refresh_from_db()
        self.assertIsNone(self.loc_a.chain_group_id)

    def test_link_allowed_for_creator(self):
        self.login(self.owner)
        resp = self.client.post(
            reverse("location_link", args=[self.loc_a.pk, self.loc_b.pk]),
        )
        self.assertEqual(resp.status_code, 302)
        self.loc_a.refresh_from_db()
        self.loc_b.refresh_from_db()
        self.assertIsNotNone(self.loc_a.chain_group_id)
        self.assertEqual(self.loc_a.chain_group_id, self.loc_b.chain_group_id)

    def test_unlink_forbidden_for_creator_without_superuser_role(self):
        # Unlink is deliberately MORE restrictive than link: creator alone
        # isn't enough, since detaching can silently drop merged item reviews.
        group = ChainGroup.objects.create()
        self.loc_a.chain_group = group
        self.loc_a.save(update_fields=["chain_group"])
        self.login(self.owner)
        resp = self.client.post(reverse("location_unlink", args=[self.loc_a.pk]))
        self.assertEqual(resp.status_code, 403)
        self.loc_a.refresh_from_db()
        self.assertIsNotNone(self.loc_a.chain_group_id)

    def test_unlink_allowed_for_superuser_role(self):
        group = ChainGroup.objects.create()
        self.loc_a.chain_group = group
        self.loc_a.save(update_fields=["chain_group"])
        self.login(self.superuser_role)
        resp = self.client.post(reverse("location_unlink", args=[self.loc_a.pk]))
        self.assertEqual(resp.status_code, 302)
        self.loc_a.refresh_from_db()
        self.assertIsNone(self.loc_a.chain_group_id)


class ItemAuthorizationTests(AppTestCase):
    def setUp(self):
        self.regular = self.make_user("regular")
        self.superuser_role = self.make_user("mod", superuser_role=True)
        self.loc = make_location(self.regular)
        self.item = Item.objects.create(location=self.loc, name="Latte")

    def test_edit_forbidden_for_regular_user(self):
        self.login(self.regular)
        resp = self.client.post(
            reverse("item_edit", args=[self.loc.pk, self.item.pk]), {"name": "Mocha"},
        )
        self.assertEqual(resp.status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Latte")

    def test_edit_allowed_for_superuser_role(self):
        self.login(self.superuser_role)
        resp = self.client.post(
            reverse("item_edit", args=[self.loc.pk, self.item.pk]), {"name": "Mocha"},
        )
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Mocha")

    def test_delete_forbidden_for_regular_user(self):
        self.login(self.regular)
        resp = self.client.post(
            reverse("item_delete", args=[self.loc.pk, self.item.pk]), {"reason": "dup"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Item.objects.filter(pk=self.item.pk).exists())

    def test_delete_allowed_for_superuser_role(self):
        self.login(self.superuser_role)
        resp = self.client.post(
            reverse("item_delete", args=[self.loc.pk, self.item.pk]), {"reason": "dup"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Item.objects.filter(pk=self.item.pk).exists())


class PhotoAuthorizationTests(AppTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp(prefix="waypoint-test-media-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.uploader = self.make_user("uploader")
        self.other = self.make_user("other")
        self.superuser_role = self.make_user("mod", superuser_role=True)
        self.loc = make_location(self.uploader)
        # Photo.save() resizes via Pillow on every save, so this needs to be a
        # real (tiny) image, not a bare filename — but the permission check
        # itself runs before the view touches the file either way.
        self.photo = Photo.objects.create(
            location=self.loc, uploaded_by=self.uploader,
            image=SimpleUploadedFile("test.png", TINY_PNG, content_type="image/png"),
        )

    def test_delete_forbidden_for_non_uploader(self):
        self.login(self.other)
        resp = self.client.post(
            reverse("photo_delete", args=[self.loc.pk, self.photo.pk]), {"reason": "bad photo"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Photo.objects.filter(pk=self.photo.pk).exists())

    def test_delete_allowed_for_uploader(self):
        self.login(self.uploader)
        resp = self.client.post(
            reverse("photo_delete", args=[self.loc.pk, self.photo.pk]), {"reason": "blurry"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Photo.objects.filter(pk=self.photo.pk).exists())

    def test_delete_allowed_for_superuser_role(self):
        self.login(self.superuser_role)
        resp = self.client.post(
            reverse("photo_delete", args=[self.loc.pk, self.photo.pk]), {"reason": "inappropriate"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Photo.objects.filter(pk=self.photo.pk).exists())

    def test_rotate_forbidden_for_non_uploader(self):
        self.login(self.other)
        resp = self.client.post(
            reverse("photo_rotate", args=[self.loc.pk, self.photo.pk]), {"direction": "cw"},
        )
        self.assertEqual(resp.status_code, 403)


class CollectionAuthorizationTests(AppTestCase):
    def setUp(self):
        self.owner = self.make_user("owner")
        self.other = self.make_user("other")
        self.superuser_role = self.make_user("mod", superuser_role=True)
        self.coll = Collection.objects.create(name="Road Trip", created_by=self.owner)

    def test_edit_forbidden_for_non_owner(self):
        self.login(self.other)
        resp = self.client.post(
            reverse("collection_edit", args=[self.coll.pk]),
            {"name": "Hijacked", "description": ""},
        )
        self.assertEqual(resp.status_code, 403)
        self.coll.refresh_from_db()
        self.assertEqual(self.coll.name, "Road Trip")

    def test_edit_allowed_for_owner(self):
        self.login(self.owner)
        resp = self.client.post(
            reverse("collection_edit", args=[self.coll.pk]),
            {"name": "Renamed Trip", "description": ""},
        )
        self.assertEqual(resp.status_code, 302)
        self.coll.refresh_from_db()
        self.assertEqual(self.coll.name, "Renamed Trip")

    def test_edit_allowed_for_superuser_role_on_someone_elses_collection(self):
        self.login(self.superuser_role)
        resp = self.client.post(
            reverse("collection_edit", args=[self.coll.pk]),
            {"name": "Moderated Name", "description": ""},
        )
        self.assertEqual(resp.status_code, 302)
        self.coll.refresh_from_db()
        self.assertEqual(self.coll.name, "Moderated Name")

    def test_delete_hides_behind_404_for_non_owner(self):
        # collection_delete looks the object up scoped to created_by=request.user,
        # so a non-owner gets 404 (object "doesn't exist" for them) rather than
        # a 403 that would at least confirm the collection exists.
        self.login(self.other)
        resp = self.client.post(
            reverse("collection_delete", args=[self.coll.pk]), {"reason": "spam"},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Collection.objects.filter(pk=self.coll.pk).exists())

    def test_toggle_public_hides_behind_404_for_non_owner(self):
        self.login(self.other)
        resp = self.client.post(reverse("collection_toggle_public", args=[self.coll.pk]))
        self.assertEqual(resp.status_code, 404)
        self.coll.refresh_from_db()
        self.assertFalse(self.coll.is_public)

    def test_feature_forbidden_for_owner_without_superuser_role(self):
        # Featuring is a superuser/admin-only spotlight — even the owner of a
        # public collection can't flip it themselves.
        self.coll.is_public = True
        self.coll.save(update_fields=["is_public"])
        self.login(self.owner)
        resp = self.client.post(reverse("collection_toggle_featured", args=[self.coll.pk]))
        self.assertEqual(resp.status_code, 403)
        self.coll.refresh_from_db()
        self.assertFalse(self.coll.is_featured)

    def test_feature_allowed_for_superuser_role_on_public_collection(self):
        self.coll.is_public = True
        self.coll.save(update_fields=["is_public"])
        self.login(self.superuser_role)
        resp = self.client.post(reverse("collection_toggle_featured", args=[self.coll.pk]))
        self.assertEqual(resp.status_code, 302)
        self.coll.refresh_from_db()
        self.assertTrue(self.coll.is_featured)

    def test_feature_refuses_a_private_collection(self):
        # is_public=True is looked up as part of the get_object_or_404 filter,
        # so a still-private collection 404s even for a superuser.
        self.login(self.superuser_role)
        resp = self.client.post(reverse("collection_toggle_featured", args=[self.coll.pk]))
        self.assertEqual(resp.status_code, 404)


class GroupMembershipAuthorizationTests(AppTestCase):
    def setUp(self):
        self.member = self.make_user("member")
        self.outsider = self.make_user("outsider")
        self.group = FriendGroup.objects.create(name="Foodies", created_by=self.member)
        FriendGroupMembership.objects.create(group=self.group, user=self.member)

    def test_invite_regenerate_forbidden_for_non_member(self):
        old_token = self.group.invite_token
        self.login(self.outsider)
        resp = self.client.post(reverse("group_invite_regenerate", args=[self.group.pk]))
        self.assertEqual(resp.status_code, 403)
        self.group.refresh_from_db()
        self.assertEqual(self.group.invite_token, old_token)

    def test_invite_regenerate_allowed_for_member(self):
        old_token = self.group.invite_token
        self.login(self.member)
        resp = self.client.post(reverse("group_invite_regenerate", args=[self.group.pk]))
        self.assertEqual(resp.status_code, 302)
        self.group.refresh_from_db()
        self.assertNotEqual(self.group.invite_token, old_token)
