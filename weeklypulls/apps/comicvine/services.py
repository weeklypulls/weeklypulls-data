import time
import logging
import datetime
from datetime import timedelta
from typing import Optional, Any, TypedDict, Dict, List
import sqlite3

from django.conf import settings
from django.utils import timezone

from simyan.comicvine import Comicvine
from simyan.schemas.issue import BasicIssue
from simyan.schemas.volume import Volume as CVVolume
from simyan.schemas.generic_entries import GenericEntry as CVPublisher
from simyan.sqlite_cache import SQLiteCache
from simyan.exceptions import ServiceError

from .models import ComicVineVolume, ComicVinePublisher

logger = logging.getLogger(__name__)


class WeeklyPrimeSummary(TypedDict):
    created: int
    updated: int
    fetched: int
    complete: bool
    next_page: int
    next_date: Optional[datetime.date]


class ComicVineService:
    """
    Service class for interacting with ComicVine API using Simyan
    with built-in rate limiting and caching.
    """

    def __init__(self):
        self.api_key: Optional[str] = settings.COMICVINE_API_KEY
        self.cache_expire_hours: int = (
            settings.COMICVINE_CACHE_EXPIRE_HOURS
            if hasattr(settings, "COMICVINE_CACHE_EXPIRE_HOURS")
            else 24 * 6
        )

        self.cv: Optional[Comicvine]
        if not self.api_key:
            logger.error("ComicVine API key not configured")
            self.cv = None
        else:
            self.cv = Comicvine(api_key=self.api_key)
            self.cv.timeout = (
                settings.COMICVINE_HTTP_TIMEOUT
                if hasattr(settings, "COMICVINE_HTTP_TIMEOUT")
                else 8
            )

    # -------------------------
    # Public API
    # -------------------------
    def get_volume(
        self, volume_id: int, force_refresh: bool = False
    ) -> Optional[ComicVineVolume]:
        """Get volume data, either from cache or API."""
        if not self.cv:
            logger.error("ComicVine API not configured")
            return None

        volume: Optional[ComicVineVolume]
        try:
            volume = ComicVineVolume.objects.get(cv_id=volume_id)
            if (
                not force_refresh
                and not volume.is_cache_expired()
                and not volume.api_fetch_failed
            ):
                return volume
        except ComicVineVolume.DoesNotExist:
            volume = None

        # Avoid retry loops on recent failures
        if volume and volume.api_fetch_failed:
            delta = timezone.now() - (volume.api_last_failure or timezone.now())
            if delta < timedelta(hours=1):
                return volume

        logger.info(f"Fetching volume {volume_id} from ComicVine API")
        start = time.time()
        try:
            cv_volume = self.cv.get_volume(volume_id)
            took_ms = int((time.time() - start) * 1000)
            logger.info(f"API SUCCESS: volume/{volume_id} - {took_ms}ms")
            volume = self._apply_cv_volume_payload(volume, cv_volume)
            return volume
        except ServiceError as e:
            took_ms = int((time.time() - start) * 1000)
            logger.error(
                f"API ERROR: volume/{volume_id} - Simyan error: {e} - {took_ms}ms"
            )
        except Exception as e:
            took_ms = int((time.time() - start) * 1000)
            logger.error(
                f"API ERROR: volume/{volume_id} - Unexpected error: {e} - {took_ms}ms"
            )

        # Mark failure
        if not volume:
            volume = ComicVineVolume(cv_id=volume_id, name=f"Volume {volume_id}")
        volume.mark_api_failure()
        volume.save()
        return volume

    def get_volume_issues(self, volume_id: int) -> List[Dict[str, Any]]:
        """Fetch issues for a volume and upsert them."""
        if not self.cv:
            logger.error("ComicVine API not configured")
            return []

        from .models import ComicVineIssue

        try:
            volume = ComicVineVolume.objects.get(cv_id=volume_id)
        except ComicVineVolume.DoesNotExist:
            v = self.get_volume(volume_id)
            if not v:
                return []
            volume = v

        start = time.time()
        issues: List[BasicIssue] = []
        page = 0
        while page < 3:
            page += 1
            page_issues = self._list_issues(
                {
                    "offset": (page - 1) * 500,
                    "filter": f"volume:{volume_id}",
                    "sort": "store_date:asc",
                }
            )
            if not page_issues:
                break
            issues.extend(page_issues)
            if len(page_issues) < 500:
                break

        took_ms = int((time.time() - start) * 1000)
        logger.info(
            f"API SUCCESS: issues for volume/{volume_id} - {len(issues)} issues - {took_ms}ms"
        )

        issue_list: List[Dict[str, Any]] = []

        for s_issue in issues:
            defaults, store_date, date_added = self._build_issue_defaults(
                s_issue, volume
            )
            ComicVineIssue.objects.update_or_create(cv_id=s_issue.id, defaults=defaults)
            issue_list.append(
                {
                    "id": s_issue.id,
                    "number": s_issue.number,
                    "name": s_issue.name,
                    "date_added": date_added,
                }
            )

        return issue_list

    def prime_issues_for_date_range(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        *,
        start_page: int = 1,
        resume_date: Optional[datetime.date] = None,
    ) -> WeeklyPrimeSummary:
        """Fetch and upsert all issues with store_date in [start_date, end_date]."""
        if not self.cv:
            logger.warning("ComicVine API not configured; skipping weekly prime")
            return {"created": 0, "updated": 0, "fetched": 0, "complete": True}

        from .models import ComicVineIssue

        total_fetched = 0
        created_count = 0
        updated_count = 0
        budget_exhausted = False

        budget_seconds = 15
        budget_start = time.time()

        cur = resume_date or start_date
        first_day = True
        last_page_used = max(1, start_page)
        resume_next_date = None
        resume_next_page = 1
        volume_cache: dict[int, Optional[ComicVineVolume]] = {}

        while cur <= end_date:
            try:
                page = max(1, start_page) if first_day else 1
                day_fetched = 0
                while True:
                    if time.time() - budget_start > budget_seconds:
                        budget_exhausted = True
                        if resume_next_date is None:
                            resume_next_date = cur
                            resume_next_page = page
                        break

                    issues = self._list_issues(
                        {
                            "offset": (page - 1) * 500,
                            "filter": f"store_date:{cur.strftime('%Y-%m-%d')}",
                            "sort": "store_date:asc",
                        }
                    )

                    if not issues:
                        break

                    day_fetched += len(issues)
                    for s_issue in issues:
                        vol = s_issue.volume
                        vol_id = vol.id
                        vol_name = vol.name

                        volume = volume_cache.get(vol_id)
                        if volume is None:
                            volume = self._ensure_volume(vol_id, vol_name, None)
                            volume_cache[vol_id] = volume
                        if volume is None:
                            continue

                        defaults, _, _ = self._build_issue_defaults(s_issue, volume)
                        ComicVineIssue.objects.update_or_create(
                            cv_id=s_issue.id, defaults=defaults
                        )

                    last_page_used = page
                    if len(issues) < 500:
                        break
                    page += 1

                total_fetched += day_fetched
            except ServiceError as e:
                logger.error(f"API ERROR: weekly issues for {cur}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error fetching weekly issues for {cur}: {e}")

            first_day = False
            start_page = 1
            cur += datetime.timedelta(days=1)

            if time.time() - budget_start > budget_seconds:
                budget_exhausted = True
                if resume_next_date is None:
                    resume_next_date = cur
                    resume_next_page = 1
                break

        complete = not budget_exhausted
        summary = {
            "created": created_count,
            "updated": updated_count,
            "fetched": total_fetched,
            "complete": complete,
            "next_page": 1 if complete else (resume_next_page or (last_page_used + 1)),
            "next_date": None if complete else resume_next_date,
        }
        logger.info(
            f"Weekly prime {start_date}..{end_date}: {summary['fetched']} fetched"
        )
        return summary

    def _ensure_utc(
        self, dt: Optional[datetime.datetime]
    ) -> Optional[datetime.datetime]:
        if dt is None:
            return None
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)

    def _list_issues(self, params: Dict[str, Any]) -> List[BasicIssue]:
        """Call Simyan list_issues, retrying once without cache if the SQLite cache
        raises a UNIQUE constraint error (seen under concurrency).
        """
        if not self.cv:
            return []
        try:
            return self.cv.list_issues(params=params)
        except ServiceError as e:
            logger.error(f"API ERROR list_issues: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in list_issues: {e}")
            return []

    def _get_or_create_publisher(
        self, payload: CVPublisher
    ) -> Optional[ComicVinePublisher]:
        if not payload:
            return None
        pub_id = payload.id
        pub_name = payload.name
        try:
            publisher_obj, _ = ComicVinePublisher.objects.get_or_create(
                cv_id=pub_id, defaults={"name": pub_name or f"Publisher {pub_id}"}
            )
            if pub_name and publisher_obj.name != pub_name:
                publisher_obj.name = pub_name
                publisher_obj.save(update_fields=["name"])
            return publisher_obj
        except Exception:
            return None

    def _ensure_volume(
        self,
        vol_id: int,
        vol_name: Optional[str],
        publisher: Optional[CVPublisher] = None,
    ) -> Optional[ComicVineVolume]:
        try:
            volume = ComicVineVolume.objects.get(cv_id=vol_id)
            if not volume.publisher:
                pub_obj = None
                if publisher:
                    pub_obj = self._get_or_create_publisher(publisher)
                if not pub_obj and self.cv:
                    try:
                        cv_volume = self.cv.get_volume(vol_id)
                        pub = (
                            cv_volume.publisher
                            if hasattr(cv_volume, "publisher")
                            else None
                        )
                        if pub is not None:
                            pub_obj = self._get_or_create_publisher(pub)
                    except BaseException:
                        pass
                if pub_obj:
                    volume.publisher = pub_obj
                    volume.save(update_fields=["publisher"])
            return volume
        except ComicVineVolume.DoesNotExist:
            publisher_obj = (
                self._get_or_create_publisher(publisher) if publisher else None
            )
            if not publisher_obj and self.cv:
                try:
                    cv_volume = self.cv.get_volume(vol_id)
                    pub = cv_volume.publisher

                    if pub is not None:
                        publisher_obj = self._get_or_create_publisher(pub)
                    vol_name = cv_volume.name
                except BaseException:
                    pass

            if not publisher_obj:
                return None

            volume = ComicVineVolume(
                cv_id=vol_id,
                name=vol_name or f"Volume {vol_id}",
                start_year=None,
                count_of_issues=0,
                publisher=publisher_obj,
                cache_expires=timezone.now() + timedelta(days=30),
            )
            volume.reset_api_failure()
            volume.save()
            return volume

    def _apply_cv_volume_payload(
        self, volume: Optional[ComicVineVolume], cv_volume: CVVolume
    ) -> ComicVineVolume:
        vol_id = cv_volume.id

        if volume is None:
            volume = ComicVineVolume(cv_id=vol_id)

        name = cv_volume.name
        volume.name = name or (f"Volume {vol_id}" if vol_id else volume.name)
        volume.start_year = cv_volume.start_year
        volume.count_of_issues = cv_volume.issue_count or 0
        pub = cv_volume.publisher

        if pub is not None:
            publisher_obj = self._get_or_create_publisher(pub)
            if publisher_obj:
                volume.publisher = publisher_obj

        volume.cache_expires = timezone.now() + timedelta(hours=self.cache_expire_hours)
        volume.reset_api_failure()
        volume.save()

        return volume

    def _build_issue_defaults(
        self, s_issue: BasicIssue, volume: ComicVineVolume
    ) -> tuple[Dict[str, Any], Optional[datetime.date], Optional[datetime.datetime]]:
        img = s_issue.image
        defaults = {
            "volume": volume,
            "date": (s_issue.store_date or s_issue.cover_date),
            "date_added": self._ensure_utc(s_issue.date_added),
            "date_last_updated": self._ensure_utc(s_issue.date_last_updated),
            "cache_expires": timezone.now() + timedelta(hours=self.cache_expire_hours),
            "image_original_url": str(img.original_url),
            "image_thumbnail_url": str(img.thumbnail),
            "image_tiny_url": str(img.tiny_url),
            "image_icon_url": str(img.icon_url),
            "image_screen_url": str(img.screen_url),
            "image_super_url": str(img.super_url),
            "image_large_screen_url": str(img.large_screen_url),
            "name": s_issue.name,
            "number": s_issue.number,
            "description": s_issue.description,
            "api_url": str(s_issue.api_url),
            "site_url": str(s_issue.site_url),
        }

        return defaults, s_issue.store_date, s_issue.date_added
