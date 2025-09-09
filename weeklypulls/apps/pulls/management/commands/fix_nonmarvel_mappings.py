import sys
import time
import logging
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
SLEEP_SECONDS = 5  # reduced fixed delay between ComicVine API calls

logger = logging.getLogger(__name__)


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
            "--delete-empty-publishers",
            action="store_true",
            help="After remapping, delete ComicVine publishers with 0 issues.",
        )

    def handle(self, *args, **options):
        apply_changes: bool = options["apply"]
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

        marvel_volume_ids = ComicVineVolume.objects.filter(
            publisher__cv_id=MARVEL_PUBLISHER_ID
        ).values_list("cv_id", flat=True)
        qs = (
            Pull.objects.exclude(series_id__in=marvel_volume_ids)
            .values_list("series_id", flat=True)
            .distinct()
        )
        if limit:
            qs = qs[:limit]
        series_ids: List[int] = list(qs)
        logger.info(
            "[fix_nonmarvel] Series to process after filtering & limit: %d",
            len(series_ids),
        )
        if series_ids:
            # Show up to first 25 IDs for context
            preview = ", ".join(str(s) for s in series_ids[:25])
            if len(series_ids) > 25:
                preview += ", ..."
            logger.debug(
                "[fix_nonmarvel] Series ID preview (first %d): %s",
                min(len(series_ids), 25),
                preview,
            )

        if not series_ids:
            self.stdout.write(self.style.WARNING("No series to process."))
            return 0

        # Build a map of cached publisher IDs (before any fresh API fetch) so we can
        # explain later why a series ended up being skipped as Marvel even though it
        # passed the initial queryset filter.
        cached_publishers_map = {}
        for v in ComicVineVolume.objects.filter(cv_id__in=series_ids).select_related(
            "publisher"
        ):
            cached_publishers_map[v.cv_id] = (
                v.publisher.cv_id if getattr(v, "publisher", None) else None
            )
        unknown_cached = sum(
            1 for _id, pid in cached_publishers_map.items() if pid is None
        )
        logger.debug(
            "[fix_nonmarvel] Cached publisher snapshot: total_cached=%d unknown_cached=%d",
            len(cached_publishers_map),
            unknown_cached,
        )

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
            logger.info(
                "[fix_nonmarvel] Fetching source volume %s (force refresh)", sid
            )
            pre_cached_pub = cached_publishers_map.get(sid)
            logger.debug(
                "[fix_nonmarvel] Pre-fetch cache state sid=%s cached_publisher=%s",
                sid,
                pre_cached_pub,
            )
            vol = svc.get_volume(sid, force_refresh=True)
            self._sleep()
            if not vol:
                self.stdout.write(
                    self.style.WARNING(f"Series {sid}: volume not found; skipping")
                )
                summary["skipped_no_match"] += 1
                continue

            pub_id = getattr(getattr(vol, "publisher", None), "cv_id", None)
            pub_name = getattr(getattr(vol, "publisher", None), "name", None)
            if pub_id == MARVEL_PUBLISHER_ID:
                logger.info(
                    (
                        "[fix_nonmarvel] Skipping Marvel series sid=%s name='%s' "
                        "pre_cached_pub=%s fetched_pub=%s reason=%s"
                    ),
                    sid,
                    vol.name,
                    pre_cached_pub,
                    pub_id,
                    (
                        "not in initial filter because publisher unknown in cache"
                        if pre_cached_pub != MARVEL_PUBLISHER_ID
                        else "already identified as Marvel"
                    ),
                )
                summary["skipped_marvel"] += 1
                continue

            # Attempt to find a Marvel volume equivalent
            logger.info(
                "[fix_nonmarvel] Searching Marvel equivalent for volume %s '%s' (%s) pub=%s",
                sid,
                vol.name,
                vol.start_year,
                pub_name,
            )
            candidate = self._find_marvel_equivalent(svc, vol)
            if not candidate:
                logger.info(
                    "[fix_nonmarvel] No Marvel match for series %s '%s' (%s) pub=%s",
                    sid,
                    vol.name,
                    vol.start_year,
                    pub_name,
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"Series {sid}: '{vol.name}' ({vol.start_year}) publisher={pub_name or 'Unknown'} -> No Marvel match"
                    )
                )
                summary["skipped_no_match"] += 1
                continue

            marvel_id, marvel_name, marvel_year = candidate

            # Ensure Marvel volume is cached and issues are present
            logger.info(
                "[fix_nonmarvel] Fetching Marvel target volume %s (force refresh)",
                marvel_id,
            )
            marvel_vol = svc.get_volume(marvel_id, force_refresh=True)
            self._sleep()
            logger.info(
                "[fix_nonmarvel] Fetching issues for Marvel volume %s to mark read",
                marvel_id,
            )
            svc.get_volume_issues(marvel_id)  # upsert issues for the volume
            self._sleep()
            issue_ids = list(
                ComicVineIssue.objects.filter(volume_id=marvel_id).values_list(
                    "cv_id", flat=True
                )
            )
            logger.debug(
                "[fix_nonmarvel] Marvel volume %s issues fetched: %d",
                marvel_id,
                len(issue_ids),
            )

            # Process pulls for this series
            pulls = list(Pull.objects.filter(series_id=sid).select_related("owner"))
            if not pulls:
                logger.info(
                    "[fix_nonmarvel] No pulls found for source series %s; skipping remap",
                    sid,
                )
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
            logger.info(
                "[fix_nonmarvel] %s series %s -> %s (pulls=%d issues=%d)",
                action,
                sid,
                marvel_id,
                len(pulls),
                len(issue_ids),
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
            logger.info(
                "[fix_nonmarvel] list_volumes query name='%s' year=%s params=%s",
                name,
                year,
                params,
            )
            results = svc.cv.list_volumes(params=params) or []
            self._sleep()
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
            logger.debug(
                "[fix_nonmarvel] Candidate chosen by exact year %s: id=%s name='%s' issues=%s",
                desired_year,
                best[0],
                best[1],
                best[3],
            )
            return (best[0], best[1], best[2])
        # Otherwise pick the candidate with the most issues as best proxy
        candidates.sort(key=lambda c: (c[3] or 0), reverse=True)
        best = candidates[0]
        logger.debug(
            "[fix_nonmarvel] Candidate chosen by issue count: id=%s name='%s' year=%s issues=%s",
            best[0],
            best[1],
            best[2],
            best[3],
        )
        return (best[0], best[1], best[2])

    def _sleep(self):
        """Sleep a fixed amount between API calls for rate limiting."""
        try:
            logger.debug(
                "[fix_nonmarvel] Sleeping %ss for rate limiting", SLEEP_SECONDS
            )
            time.sleep(SLEEP_SECONDS)
        except Exception:
            pass
