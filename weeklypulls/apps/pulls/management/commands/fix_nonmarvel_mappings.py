import sys
from typing import Iterable, List, Optional, Tuple

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.db.models import Count

from weeklypulls.apps.pulls.models import Pull
from weeklypulls.apps.comicvine.models import (
    ComicVineIssue,
    ComicVinePublisher,
    ComicVineVolume,
)
from weeklypulls.apps.comicvine.services import ComicVineService


MARVEL_PUBLISHER_ID = 31


class Command(BaseCommand):
    help = (
        "Find series mapped to non-Marvel publishers, locate the original Marvel "
        "volume via ComicVine, repoint pulls, and mark all issues as read."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Execute changes. Without this flag, runs in dry-run mode.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit the number of distinct series IDs to process.",
        )
        parser.add_argument(
            "--series-id",
            action="append",
            type=int,
            default=None,
            help="Restrict to one or more specific series IDs (can be repeated).",
        )
        parser.add_argument(
            "--delete-empty-publishers",
            action="store_true",
            help="After remapping, delete ComicVine publishers with 0 issues.",
        )

    def handle(self, *args, **options):
        apply_changes: bool = options["apply"]
        series_filter: Optional[List[int]] = options.get("series_id")
        limit: Optional[int] = options.get("limit")
        delete_empty_publishers: bool = options.get("delete_empty_publishers")

        svc = ComicVineService()
        if not getattr(svc, "cv", None):
            self.stderr.write(
                self.style.ERROR(
                    "ComicVine API not configured (missing COMICVINE_API_KEY)."
                )
            )
            return 2

        # Build the list of distinct series IDs referenced by pulls
        qs = Pull.objects.all().values_list("series_id", flat=True).distinct()
        if series_filter:
            qs = qs.filter(series_id__in=series_filter)
        series_ids: List[int] = list(qs[: limit or 1000000])

        if not series_ids:
            self.stdout.write(self.style.WARNING("No series to process."))
            return 0

        summary = {
            "considered": 0,
            "skipped_marvel": 0,
            "skipped_no_match": 0,
            "remapped": 0,
            "merged_pulls": 0,
            "issues_marked_read": 0,
            "publishers_deleted": 0,
        }

        for sid in series_ids:
            summary["considered"] += 1
            # Always refresh volume from API to avoid stale/foreign cached data
            vol = svc.get_volume(sid, force_refresh=True)
            if not vol:
                self.stdout.write(
                    self.style.WARNING(f"Series {sid}: volume not found; skipping")
                )
                summary["skipped_no_match"] += 1
                continue

            pub_id = getattr(getattr(vol, "publisher", None), "cv_id", None)
            pub_name = getattr(getattr(vol, "publisher", None), "name", None)
            if pub_id == MARVEL_PUBLISHER_ID:
                summary["skipped_marvel"] += 1
                continue

            # Attempt to find a Marvel volume equivalent
            candidate = self._find_marvel_equivalent(svc, vol)
            if not candidate:
                self.stdout.write(
                    self.style.WARNING(
                        f"Series {sid}: '{vol.name}' ({vol.start_year}) publisher={pub_name or 'Unknown'} -> No Marvel match"
                    )
                )
                summary["skipped_no_match"] += 1
                continue

            marvel_id, marvel_name, marvel_year = candidate

            # Ensure Marvel volume is cached and issues are present
            marvel_vol = svc.get_volume(marvel_id, force_refresh=True)
            svc.get_volume_issues(marvel_id)  # upsert issues for the volume
            issue_ids = list(
                ComicVineIssue.objects.filter(volume_id=marvel_id).values_list(
                    "cv_id", flat=True
                )
            )

            # Process pulls for this series
            pulls = list(Pull.objects.filter(series_id=sid).select_related("owner"))
            if not pulls:
                continue

            # Apply or dry-run
            if apply_changes:
                with transaction.atomic():
                    for p in pulls:
                        # Try to merge into an existing destination pull for the same owner
                        dest = Pull.objects.filter(
                            owner=p.owner, series_id=marvel_id
                        ).first()
                        if dest:
                            # Merge read lists, then set to all issues in Marvel volume
                            dest.read = sorted(set(issue_ids))
                            dest.save(update_fields=["read"])
                            # Remove the old pull
                            p.delete()
                            summary["merged_pulls"] += 1
                        else:
                            # Update in place
                            p.series_id = marvel_id
                            p.read = sorted(set(issue_ids))
                            p.save(update_fields=["series_id", "read", "modified_at"])
                        summary["issues_marked_read"] += len(issue_ids)
                action = "UPDATED"
            else:
                action = "WOULD UPDATE"

            summary["remapped"] += 1
            self.stdout.write(
                f"{action}: series {sid} -> {marvel_id}  "
                f"{vol.name} ({vol.start_year}) [{pub_name or 'Unknown'}]  "
                f"=> {marvel_name} ({marvel_year}) [Marvel]  "
                f"pulls={len(pulls)} issues={len(issue_ids)}"
            )

        # Optional cleanup: delete publishers with 0 issues
        if delete_empty_publishers:
            to_delete = (
                ComicVinePublisher.objects.annotate(
                    issue_count=Count("volumes__issues")
                )
                .filter(issue_count=0)
                .values_list("cv_id", "name")
            )
            count = len(list(to_delete))
            if apply_changes and count:
                ComicVinePublisher.objects.annotate(
                    issue_count=Count("volumes__issues")
                ).filter(issue_count=0).delete()
            summary["publishers_deleted"] = count if apply_changes else 0
            self.stdout.write(
                ("DELETED" if apply_changes else "WOULD DELETE")
                + f" publishers with 0 issues: {count}"
            )

        # Final summary
        self.stdout.write(
            self.style.SUCCESS(
                "Done: " + ", ".join(f"{k}={v}" for k, v in summary.items())
            )
        )
        return 0

    # ---------------------
    # Helper methods
    # ---------------------
    def _find_marvel_equivalent(
        self, svc: ComicVineService, vol: ComicVineVolume
    ) -> Optional[Tuple[int, str, Optional[int]]]:
        """
        Find the Marvel volume matching the given non-Marvel volume by name and year.

        Returns (marvel_id, name, start_year) or None.
        """
        name = (vol.name or "").strip()
        year = vol.start_year

        # First try name + year + Marvel publisher
        candidates = self._search_volumes(svc, name=name, year=year)
        chosen = self._choose_candidate(candidates, year)
        if chosen:
            return chosen

        # Fallback: name only under Marvel; choose best by exact-year or issue count
        candidates = self._search_volumes(svc, name=name, year=None)
        chosen = self._choose_candidate(candidates, year)
        return chosen

    def _search_volumes(
        self, svc: ComicVineService, *, name: str, year: Optional[int]
    ) -> List[Tuple[int, str, Optional[int], int]]:
        """
        Return list of candidates as tuples: (id, name, start_year, issue_count)
        filtered to Marvel publisher.
        """
        try:
            params = {"filter": f"publisher:{MARVEL_PUBLISHER_ID},name:{name}"}
            # ComicVine supports filtering by start_year as well
            if year:
                params["filter"] += f",start_year:{year}"
            params["sort"] = "count_of_issues:desc"
            results = svc.cv.list_volumes(params=params) or []
        except Exception:
            results = []

        out: List[Tuple[int, str, Optional[int], int]] = []
        for r in results:
            try:
                out.append(
                    (
                        r.id,
                        r.name,
                        getattr(r, "start_year", None),
                        getattr(r, "issue_count", 0),
                    )
                )
            except Exception:
                continue
        return out

    def _choose_candidate(
        self,
        candidates: List[Tuple[int, str, Optional[int], int]],
        desired_year: Optional[int],
    ) -> Optional[Tuple[int, str, Optional[int]]]:
        if not candidates:
            return None
        # Prefer exact year match
        exact = [
            c for c in candidates if c[2] and desired_year and c[2] == desired_year
        ]
        if exact:
            # Among exact year matches, pick the one with most issues
            exact.sort(key=lambda c: (c[3] or 0), reverse=True)
            best = exact[0]
            return (best[0], best[1], best[2])
        # Otherwise pick the candidate with the most issues as best proxy
        candidates.sort(key=lambda c: (c[3] or 0), reverse=True)
        best = candidates[0]
        return (best[0], best[1], best[2])
