import logging
from typing import Optional

from django.core.management.base import BaseCommand, CommandParser
from django.contrib.auth import get_user_model
from django.db import transaction

from weeklypulls.apps.comicvine.models import ComicVineVolume
from weeklypulls.apps.pulls.models import Pull

logger = logging.getLogger(__name__)

MARVEL_PUBLISHER_ID = 31


class Command(BaseCommand):
    help = (
        "Create Pull entries for a given user for every non-Marvel ComicVineVolume "
        "(publisher not null and not Marvel) that currently has no pull for that user."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Execute changes. Without this flag, runs in dry-run mode.",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=1,
            help="User ID to create pulls for (default: 1)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Optional limit on number of pulls to create",
        )

    def handle(self, *args, **options):  # type: ignore[override]
        apply_changes: bool = options["apply"]
        user_id: int = options["user_id"]
        limit: Optional[int] = options.get("limit")

        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"User id {user_id} not found"))
            return 2

        # Volumes that are explicitly non-Marvel, have a publisher, and not already pulled by this user
        non_marvel_vol_ids = list(
            ComicVineVolume.objects.exclude(publisher__cv_id=MARVEL_PUBLISHER_ID)
            .exclude(publisher__isnull=True)
            .values_list("cv_id", flat=True)
        )
        existing_pull_series = set(
            Pull.objects.filter(owner=user).values_list("series_id", flat=True)
        )
        candidates = [
            vid for vid in non_marvel_vol_ids if vid not in existing_pull_series
        ]

        if limit is not None:
            candidates = candidates[:limit]

        if not candidates:
            self.stdout.write(
                self.style.WARNING("No missing non-Marvel pulls to create.")
            )
            return 0

        created = 0
        for idx, series_id in enumerate(candidates, start=1):
            if apply_changes:
                with transaction.atomic():
                    Pull.objects.create(owner=user, series_id=series_id)
                created += 1
                self.stdout.write(
                    f"CREATED pull {idx}/{len(candidates)} series={series_id} user={user_id}"
                )
            else:
                self.stdout.write(
                    f"WOULD CREATE pull {idx}/{len(candidates)} series={series_id} user={user_id}"
                )

        summary_msg = (
            f"Done: created={created} total_candidates={len(candidates)} user={user_id} "
            f"mode={'apply' if apply_changes else 'dry-run'}"
        )
        self.stdout.write(self.style.SUCCESS(summary_msg))
        return 0
