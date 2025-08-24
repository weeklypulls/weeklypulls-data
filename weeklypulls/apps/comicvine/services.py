import time
import logging
import datetime
from datetime import timedelta
from typing import Optional
from django.conf import settings
from django.utils import timezone
from dateutil.parser import parse

from simyan.comicvine import Comicvine
from simyan.sqlite_cache import SQLiteCache
from simyan.exceptions import ServiceError

from .models import ComicVineVolume, ComicVinePublisher

logger = logging.getLogger(__name__)


class ComicVineService:
    """
    Service class for interacting with ComicVine API using Simyan
    with built-in rate limiting and caching.
    """

    def __init__(self):
        self.api_key = settings.COMICVINE_API_KEY
        self.cache_expire_hours = getattr(
            settings, "COMICVINE_CACHE_EXPIRE_HOURS", 24 * 6
        )  # 6 days default

        if not self.api_key:
            logger.error("ComicVine API key not configured")
            self.cv = None
        else:
            # Initialize Simyan with built-in SQLite caching
            cache = SQLiteCache()
            self.cv = Comicvine(api_key=self.api_key, cache=cache)
            # Ensure HTTP calls have a finite timeout to avoid worker hangs
            try:
                self.cv.timeout = getattr(settings, "COMICVINE_HTTP_TIMEOUT", 8)
            except Exception:
                pass

    def get_volume(
        self, volume_id: int, force_refresh: bool = False
    ) -> Optional[ComicVineVolume]:
        """
        Get volume data, either from cache or API

        Args:
            volume_id: ComicVine volume ID
            force_refresh: Force API call even if cached data exists

        Returns:
            ComicVineVolume instance or None if failed
        """
        if not self.cv:
            logger.error("ComicVine API not configured")
            return None

        try:
            volume = ComicVineVolume.objects.get(cv_id=volume_id)

            # Return cached data if it's fresh and no force refresh
            if (
                not force_refresh
                and not volume.is_cache_expired()
                and not volume.api_fetch_failed
            ):
                logger.debug(f"Returning cached volume data for {volume_id}")
                return volume

        except ComicVineVolume.DoesNotExist:
            volume = None

        # Don't retry failed API calls too frequently
        if volume and volume.api_fetch_failed:
            time_since_failure = timezone.now() - (
                volume.api_last_failure or timezone.now()
            )
            if time_since_failure < timedelta(hours=1):
                logger.debug(
                    f"Skipping API call for volume {volume_id} due to recent failure"
                )
                return volume

        # Fetch from API using Simyan (handles rate limiting automatically)
        logger.info(f"Fetching volume {volume_id} from ComicVine API")
        start_time = time.time()

        try:
            # Use Simyan to get volume - it handles rate limiting and caching
            cv_volume = self.cv.get_volume(volume_id)
            response_time_ms = int((time.time() - start_time) * 1000)

            # Log successful API call
            logger.info(f"API SUCCESS: volume/{volume_id} - {response_time_ms}ms")

            # Create or update volume
            if not volume:
                volume = ComicVineVolume(cv_id=volume_id)

            # Explicit attribute access (fail fast if Simyan API changes)
            volume.name = cv_volume.name or f"Volume {volume_id}"
            volume.start_year = cv_volume.start_year
            volume.count_of_issues = (
                cv_volume.issue_count or 0
            )  # Simyan uses issue_count
            # Publisher (FK) — create/update lightweight publisher row and link
            try:
                pub = getattr(cv_volume, "publisher", None)
                pub_id = getattr(pub, "id", None) if pub else None
                pub_name = getattr(pub, "name", None) if pub else None
                if pub_id is not None:
                    publisher_obj, _ = ComicVinePublisher.objects.get_or_create(
                        cv_id=pub_id,
                        defaults={"name": pub_name or f"Publisher {pub_id}"},
                    )
                    if pub_name and publisher_obj.name != pub_name:
                        publisher_obj.name = pub_name
                        publisher_obj.save(update_fields=["name"])
                    volume.publisher = publisher_obj
                else:
                    volume.publisher = None
            except Exception:
                volume.publisher = None
            volume.cache_expires = timezone.now() + timedelta(
                hours=self.cache_expire_hours
            )

            # Reset failure status on successful fetch
            volume.reset_api_failure()
            volume.save()

            logger.info(f"Successfully cached volume {volume_id}: {volume.name}")
            return volume

        except ServiceError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Simyan ComicVine error: {str(e)}"
            logger.error(
                f"API ERROR: volume/{volume_id} - {error_msg} - {response_time_ms}ms"
            )

            # Mark API failure
            if not volume:
                volume = ComicVineVolume(cv_id=volume_id, name=f"Volume {volume_id}")
            volume.mark_api_failure()
            volume.save()
            return volume

        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(
                f"API ERROR: volume/{volume_id} - {error_msg} - {response_time_ms}ms"
            )

            # Mark API failure
            if not volume:
                volume = ComicVineVolume(cv_id=volume_id, name=f"Volume {volume_id}")
            volume.mark_api_failure()
            volume.save()
            return volume

    def get_volume_issues(self, volume_id: int) -> list:
        """
        Get issues for a volume, sorted by issue number/date, continuing from where we left off.
        Also saves the issues to the database.

        Args:
            volume_id: ComicVine volume ID

        Returns:
            List of issue dictionaries with id, issue_number, name, date_added
        """
        if not self.cv:
            logger.error("ComicVine API not configured")
            return []

        try:
            # Get the ComicVineVolume instance
            from .models import ComicVineVolume, ComicVineIssue

            try:
                volume = ComicVineVolume.objects.get(cv_id=volume_id)
            except ComicVineVolume.DoesNotExist:
                logger.error(f"ComicVineVolume {volume_id} not found in database")
                return []

            logger.info(f"Fetching issues for volume {volume_id})")
            start_time = time.time()
            issues = []
            page = 0
            existing_count = ComicVineIssue.objects.filter(volume=volume).count()

            # Keep fetching while we need more issues and haven't hit page limit
            while (
                len(issues) == 0
                or (volume.count_of_issues > 0 and len(issues) < volume.count_of_issues)
            ) and page < 3:
                page += 1
                logger.info(f"Fetching issues for volume {volume_id}, page {page}")
                page_issues = self.cv.list_issues(
                    params={
                        "offset": (page - 1) * 500,  # Fix offset calculation
                        "filter": f"volume:{volume_id}",
                        "sort": "store_date:asc",  # Use store_date instead of issue_number
                    },
                )
                issues.extend(page_issues)  # Use extend() not append()

            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"API SUCCESS: issues for volume/{volume_id} - {len(issues)} issues - {response_time_ms}ms"
            )

            # Convert to simple list of dicts AND save to database
            issue_list = []
            created_count = 0
            updated_count = 0

            for s_issue in issues:
                defaults, store_date, date_added = self._build_issue_defaults(
                    s_issue, volume
                )

                comic_issue, created = ComicVineIssue.objects.update_or_create(
                    cv_id=s_issue.id, defaults=defaults
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

                # Add to return list (inline values)
                issue_list.append(
                    {
                        "id": s_issue.id,
                        "number": s_issue.number,
                        "name": s_issue.name,
                        "date_added": date_added,
                    }
                )

            logger.info(
                f"Processed volume {volume_id}: {created_count} created, {updated_count} updated, (total now: {existing_count + created_count})"
            )
            return issue_list

        except ServiceError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"API ERROR: issues for volume/{volume_id} - Simyan error: {str(e)} - {response_time_ms}ms"
            )
            return []

        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"API ERROR: issues for volume/{volume_id} - Unexpected error: {str(e)} - {response_time_ms}ms"
            )
            return []

    def prime_issues_for_date_range(
        self, start_date, end_date, *, start_page: int = 1, resume_date=None
    ) -> dict:
        """Fetch and upsert all issues with store_date in [start_date, end_date].

        Returns a summary dict with counts and a 'complete' flag indicating
        whether the pass finished within the time budget. Safe to call if API key missing.
        """
        if not self.cv:
            logger.warning("ComicVine API not configured; skipping weekly prime")
            return {"created": 0, "updated": 0, "fetched": 0, "complete": True}

        from .models import (
            ComicVineIssue,
            ComicVineVolume,
        )  # local import to avoid cycles

        total_fetched = 0
        created_count = 0
        updated_count = 0
        budget_exhausted = False

        # Overall time budget for this priming call to protect request latency
        budget_seconds = getattr(settings, "COMICVINE_PRIME_BUDGET_SECONDS", 6)
        budget_start = time.time()

        # Iterate each day to avoid uncertain API range filter syntax
        # If resuming, start from resume_date; otherwise start at start_date
        cur = resume_date or start_date
        first_day = True
        last_page_used = max(1, start_page)
        resume_next_date = None
        resume_next_page = 1

        while cur <= end_date:
            try:
                page = max(1, start_page) if first_day else 1
                day_fetched = 0
                while page <= 3:  # reasonable safety limit
                    # Respect overall time budget
                    if time.time() - budget_start > budget_seconds:
                        budget_exhausted = True
                        # Resume on the same day/page we were about to fetch
                        if resume_next_date is None:
                            resume_next_date = cur
                            resume_next_page = page
                        break
                    issues = self.cv.list_issues(
                        params={
                            "offset": (page - 1) * 500,
                            "filter": f"store_date:{cur.strftime('%Y-%m-%d')}",
                            "sort": "store_date:asc",
                        },
                    )
                    if not issues:
                        break
                    day_fetched += len(issues)
                    for s_issue in issues:
                        # Ensure volume exists/updated minimally
                        vol = getattr(s_issue, "volume", None)
                        vol_id = getattr(vol, "id", None)
                        vol_name = getattr(vol, "name", None)
                        pub_payload = None
                        try:
                            pub = getattr(vol, "publisher", None)
                            pub_id = getattr(pub, "id", None) if pub else None
                            pub_name = getattr(pub, "name", None) if pub else None
                            if pub_id is not None:
                                pub_payload = {"id": pub_id, "name": pub_name}
                        except Exception:
                            pub_payload = None
                        if vol_id is None:
                            # skip issues without a volume id
                            continue
                        volume = self._ensure_volume(vol_id, vol_name, pub_payload)

                        defaults, _, _ = self._build_issue_defaults(s_issue, volume)

                        ComicVineIssue.objects.update_or_create(
                            cv_id=s_issue.id, defaults=defaults
                        )
                        # Track CRUD metrics
                        # We can't distinguish easily here without extra query costs; count fetched only
                        # created_count/updated_count are less important than fetched for budgeting

                    last_page_used = page
                    # Stop paging the day if fewer than a full page returned
                    if len(issues) < 500:
                        break
                    page += 1

                total_fetched += day_fetched
            except ServiceError as e:
                logger.error(f"API ERROR: weekly issues for {cur}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error fetching weekly issues for {cur}: {e}")

            # After the first day, resume from page 1 for subsequent days
            first_day = False
            start_page = 1
            cur += datetime.timedelta(days=1)

            # Stop if over budget
            if time.time() - budget_start > budget_seconds:
                budget_exhausted = True
                # Resume on the next day at page 1
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
            # Provide resume hints when not complete
            "next_page": 1 if complete else (resume_next_page or (last_page_used + 1)),
            "next_date": None if complete else resume_next_date,
        }
        logger.info(
            f"Weekly prime {start_date}..{end_date}: {summary['fetched']} fetched"
        )
        return summary

    # -------------------------
    # Internal helpers (DRY)
    # -------------------------
    def _parse_date(self, raw):
        if not raw:
            return None
        try:
            if isinstance(raw, datetime.date) and not isinstance(
                raw, datetime.datetime
            ):
                return raw
            if isinstance(raw, datetime.datetime):
                return raw.date()
            return parse(raw).date()
        except Exception:
            return None

    def _parse_datetime_utc(self, raw):
        if not raw:
            return None
        try:
            if isinstance(raw, (datetime.date, datetime.datetime)):
                dt = raw
            else:
                dt = parse(raw)
            if isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
                # promote date to datetime midnight UTC
                dt = datetime.datetime(dt.year, dt.month, dt.day)
            if timezone.is_naive(dt):
                return timezone.make_aware(dt, datetime.timezone.utc)
            return dt.astimezone(datetime.timezone.utc)
        except Exception:
            return None

    def _get_img(self, img, attr):
        return getattr(img, attr, None) if img is not None else None

    def _ensure_volume(
        self, vol_id: int, vol_name: str, publisher: Optional[dict] = None
    ):
        from .models import ComicVineVolume  # local import

        try:
            volume = ComicVineVolume.objects.get(cv_id=vol_id)
            # Backfill publisher FK if available and missing
            if publisher and not getattr(volume, "publisher", None):
                from .models import ComicVinePublisher as _CVP

                pub_id = publisher.get("id")
                pub_name = publisher.get("name")
                if pub_id is not None:
                    publisher_obj, _ = _CVP.objects.get_or_create(
                        cv_id=pub_id,
                        defaults={"name": pub_name or f"Publisher {pub_id}"},
                    )
                    if pub_name and publisher_obj.name != pub_name:
                        publisher_obj.name = pub_name
                        publisher_obj.save(update_fields=["name"])
                    volume.publisher = publisher_obj
                    volume.save(update_fields=["publisher"])
            return volume
        except ComicVineVolume.DoesNotExist:
            # Create publisher if provided
            publisher_obj = None
            if publisher:
                from .models import ComicVinePublisher as _CVP

                pub_id = publisher.get("id")
                pub_name = publisher.get("name")
                if pub_id is not None:
                    publisher_obj, _ = _CVP.objects.get_or_create(
                        cv_id=pub_id,
                        defaults={"name": pub_name or f"Publisher {pub_id}"},
                    )
                    if pub_name and publisher_obj.name != pub_name:
                        publisher_obj.name = pub_name
                        publisher_obj.save(update_fields=["name"])
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

    def _build_issue_defaults(self, s_issue, volume):
        store_date = self._parse_date(getattr(s_issue, "store_date", None))
        cover_date = self._parse_date(getattr(s_issue, "cover_date", None))
        date_added = self._parse_datetime_utc(getattr(s_issue, "date_added", None))
        date_last_updated = self._parse_datetime_utc(
            getattr(s_issue, "date_last_updated", None)
        )
        img = getattr(s_issue, "image", None)

        defaults = {
            "name": getattr(s_issue, "name", None),
            "number": getattr(s_issue, "number", None),
            "volume": volume,
            # canonical sale date only
            "date": store_date or cover_date,
            "description": getattr(s_issue, "description", None),
            "date_added": date_added,
            "date_last_updated": date_last_updated,
            "api_url": getattr(s_issue, "api_url", None),
            "site_url": getattr(s_issue, "site_url", None),
            "cache_expires": timezone.now() + timedelta(days=30),
            "image_icon_url": self._get_img(img, "icon_url"),
            "image_thumbnail_url": self._get_img(img, "thumbnail"),
            "image_tiny_url": self._get_img(img, "tiny_url"),
            "image_small_url": self._get_img(img, "small_url"),
            "image_medium_url": self._get_img(img, "medium_url")
            or self._get_img(img, "super_url")
            or self._get_img(img, "screen_url")
            or self._get_img(img, "small_url")
            or self._get_img(img, "original_url")
            or self._get_img(img, "thumbnail")
            or self._get_img(img, "tiny_url")
            or self._get_img(img, "icon_url"),
            "image_screen_url": self._get_img(img, "screen_url"),
            "image_super_url": self._get_img(img, "super_url"),
            "image_large_screen_url": self._get_img(img, "large_screen_url"),
            "image_original_url": self._get_img(img, "original_url"),
        }
        return defaults, store_date, date_added
