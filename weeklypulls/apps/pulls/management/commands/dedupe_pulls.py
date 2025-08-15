from django.core.management.base import BaseCommand
from django.db import transaction
from collections import defaultdict

from weeklypulls.apps.pulls.models import Pull


class Command(BaseCommand):
    help = "Deduplicate Pulls by (owner, series_id), keeping the one with the most read entries and merging reads"

    def handle(self, *args, **options):
        # Build groups: (owner_id, series_id) -> list[Pull]
        groups = defaultdict(list)
        qs = Pull.objects.select_related("pull_list__owner").only(
            "id", "owner_id", "series_id", "read", "pull_list__owner"
        )
        for p in qs:
            owner_id = p.owner_id or getattr(
                getattr(p, "pull_list", None), "owner_id", None
            )
            if owner_id is None:
                # Skip weird records; should not happen once owner is enforced
                continue
            groups[(owner_id, p.series_id)].append(p)

        total_groups = len(groups)
        removed = 0
        merged = 0
        self.stdout.write(f"Found {total_groups} (owner, series) groups to inspect")

        with transaction.atomic():
            for key, pulls in groups.items():
                if len(pulls) <= 1:
                    # For singletons, ensure owner is set
                    p = pulls[0]
                    if p.owner_id is None:
                        p.owner_id = p.pull_list.owner_id
                        p.save(update_fields=["owner_id"])
                    continue

                # Choose canonical: most read entries; tie-breaker: smallest UUID string for stability
                def read_count(p):
                    return len(p.read or [])

                pulls_sorted = sorted(
                    pulls,
                    key=lambda x: (-read_count(x), str(x.id)),
                )
                keep = pulls_sorted[0]
                to_delete = pulls_sorted[1:]

                # Merge reads from others into keep
                keep_set = set(keep.read or [])
                for p in to_delete:
                    merged += len(set(p.read or []) - keep_set)
                    keep_set.update(p.read or [])
                if keep.read != list(keep_set):
                    keep.read = list(keep_set)
                    keep.save(update_fields=["read"])

                # Ensure owner set on keep
                if keep.owner_id is None:
                    keep.owner_id = keep.pull_list.owner_id
                    keep.save(update_fields=["owner_id"])

                # Delete duplicates
                for p in to_delete:
                    p.delete()
                    removed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Deduped pulls. Removed={removed}, merged_reads={merged}"
            )
        )
