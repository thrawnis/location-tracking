from django.core.management.base import BaseCommand
from django.db import transaction

from tracker.models import Location, OsmSearchCache


class Command(BaseCommand):
    help = (
        "Delete all saved Locations (and their cascaded visits, items, photos, "
        "reviews, and collection memberships). Intended for wiping legacy "
        "OSM-era waypoints before real use. Also clears the OSM search cache."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the interactive confirmation prompt.",
        )
        parser.add_argument(
            "--keep-cache",
            action="store_true",
            help="Do not clear the OsmSearchCache table.",
        )

    def handle(self, *args, **options):
        loc_count = Location.objects.count()
        cache_count = 0 if options["keep_cache"] else OsmSearchCache.objects.count()

        if loc_count == 0 and cache_count == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to delete — already empty."))
            return

        self.stdout.write(
            "This will permanently delete {} location(s) and everything attached "
            "to them (visits, items, photos, reviews, collection links){}.".format(
                loc_count,
                "" if options["keep_cache"] else ", plus {} cache row(s)".format(cache_count),
            )
        )

        if not options["yes"]:
            confirm = input("Type 'yes' to proceed: ").strip().lower()
            if confirm != "yes":
                self.stdout.write(self.style.WARNING("Aborted — nothing was deleted."))
                return

        with transaction.atomic():
            Location.objects.all().delete()
            if not options["keep_cache"]:
                OsmSearchCache.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                "Deleted {} location(s){}.".format(
                    loc_count,
                    "" if options["keep_cache"] else " and {} cache row(s)".format(cache_count),
                )
            )
        )
