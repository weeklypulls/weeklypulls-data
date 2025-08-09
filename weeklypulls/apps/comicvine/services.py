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

from .models import ComicVineVolume

logger = logging.getLogger(__name__)


class ComicVineService:
    """
    Service class for interacting with ComicVine API using Simyan
    with built-in rate limiting and caching.
    """
    
    def __init__(self):
        self.api_key = settings.COMICVINE_API_KEY
        self.cache_expire_hours = getattr(settings, 'COMICVINE_CACHE_EXPIRE_HOURS', 24 * 6)  # 6 days default
        
        if not self.api_key:
            logger.error("ComicVine API key not configured")
            self.cv = None
        else:
            # Initialize Simyan with built-in SQLite caching
            cache = SQLiteCache()
            self.cv = Comicvine(api_key=self.api_key, cache=cache)
    
    def get_volume(self, volume_id: int, force_refresh: bool = False) -> Optional[ComicVineVolume]:
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
            if not force_refresh and not volume.is_cache_expired() and not volume.api_fetch_failed:
                logger.debug(f"Returning cached volume data for {volume_id}")
                return volume
                
        except ComicVineVolume.DoesNotExist:
            volume = None
        
        # Don't retry failed API calls too frequently
        if volume and volume.api_fetch_failed:
            time_since_failure = timezone.now() - (volume.api_last_failure or timezone.now())
            if time_since_failure < timedelta(hours=1):
                logger.debug(f"Skipping API call for volume {volume_id} due to recent failure")
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
            volume.count_of_issues = cv_volume.issue_count or 0  # Simyan uses issue_count
            volume.cache_expires = timezone.now() + timedelta(hours=self.cache_expire_hours)
            
            # Reset failure status on successful fetch
            volume.reset_api_failure()
            volume.save()
            
            logger.info(f"Successfully cached volume {volume_id}: {volume.name}")
            return volume
            
        except ServiceError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Simyan ComicVine error: {str(e)}"
            logger.error(f"API ERROR: volume/{volume_id} - {error_msg} - {response_time_ms}ms")
            
            # Mark API failure
            if not volume:
                volume = ComicVineVolume(cv_id=volume_id, name=f"Volume {volume_id}")
            volume.mark_api_failure()
            volume.save()
            return volume
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"API ERROR: volume/{volume_id} - {error_msg} - {response_time_ms}ms")
            
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
            while (len(issues) == 0 or (volume.count_of_issues > 0 and len(issues) < volume.count_of_issues)) and page < 3:
                page += 1
                logger.info(f"Fetching issues for volume {volume_id}, page {page}")
                page_issues = self.cv.list_issues(
                    params={
                        'offset': (page - 1) * 500,  # Fix offset calculation
                        'filter': f'volume:{volume_id}',
                        'sort': 'store_date:asc'  # Use store_date instead of issue_number
                    },
                )
                issues.extend(page_issues)  # Use extend() not append()
            
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"API SUCCESS: issues for volume/{volume_id} - {len(issues)} issues - {response_time_ms}ms")
            
            # Convert to simple list of dicts AND save to database
            issue_list = []
            created_count = 0
            updated_count = 0
            
            for issue in issues:
                # Parse dates with better error handling
                store_date = None
                cover_date = None
                date_added = None
                date_last_updated = None
                
                # Parse store_date
                raw = issue.store_date
                if raw:
                    try:
                        if isinstance(raw, datetime.date) and not isinstance(raw, datetime.datetime):
                            store_date = raw
                        elif isinstance(raw, datetime.datetime):
                            store_date = raw.date()
                        else:
                            store_date = parse(raw).date()
                    except Exception as e:
                        print(f"Failed to parse store_date '{raw}' for issue {issue.id}: {e}")
                        
                # Parse cover_date
                raw = issue.cover_date
                if raw:
                    try:
                        if isinstance(raw, datetime.date) and not isinstance(raw, datetime.datetime):
                            cover_date = raw
                        elif isinstance(raw, datetime.datetime):
                            cover_date = raw.date()
                        else:
                            cover_date = parse(raw).date()
                    except Exception as e:
                        print(f"Failed to parse cover_date '{raw}' for issue {issue.id}: {e}")
                        
                # Parse date_added
                raw = issue.date_added
                if raw:
                    try:
                        if isinstance(raw, (datetime.date, datetime.datetime)):
                            date_added = raw
                        else:
                            date_added = parse(raw)
                    except Exception as e:
                        print(f"Failed to parse date_added '{raw}' for issue {issue.id}: {e}")
                # Ensure timezone-aware UTC
                if isinstance(date_added, datetime.datetime):
                    if timezone.is_naive(date_added):
                        date_added = timezone.make_aware(date_added, datetime.timezone.utc)
                    else:
                        date_added = date_added.astimezone(datetime.timezone.utc)
                        
                # Parse date_last_updated
                raw = issue.date_last_updated
                if raw:
                    try:
                        if isinstance(raw, (datetime.date, datetime.datetime)):
                            date_last_updated = raw
                        else:
                            date_last_updated = parse(raw)
                    except Exception as e:
                        print(f"Failed to parse date_last_updated '{raw}' for issue {issue.id}: {e}")
                # Ensure timezone-aware UTC
                if isinstance(date_last_updated, datetime.datetime):
                    if timezone.is_naive(date_last_updated):
                        date_last_updated = timezone.make_aware(date_last_updated, datetime.timezone.utc)
                    else:
                        date_last_updated = date_last_updated.astimezone(datetime.timezone.utc)
                
                # Image URLs (explicit fields)
                img = issue.image

                # Create or update ComicVineIssue record (inline values, no temps)
                issue_data = {
                    'name': issue.name,
                    'number': issue.number,
                    'volume': volume,
                    'store_date': store_date,
                    'cover_date': cover_date,
                    'description': issue.description,
                    'date_added': date_added,
                    'date_last_updated': date_last_updated,
                    'api_url': issue.api_url,
                    'site_url': issue.site_url,
                    'cache_expires': timezone.now() + timedelta(days=30),
                    'image_icon_url': img.icon_url,
                    'image_thumbnail_url': img.thumbnail,
                    'image_tiny_url': img.tiny_url,
                    'image_small_url': img.small_url,
                    'image_medium_url': (
                        img.medium_url or img.super_url or img.screen_url or img.small_url
                        or img.original_url or img.thumbnail or img.tiny_url or img.icon_url
                    ),
                    'image_screen_url': img.screen_url,
                    'image_super_url': img.super_url,
                    'image_large_screen_url': img.large_screen_url,
                    'image_original_url': img.original_url,
                }
                
                comic_issue, created = ComicVineIssue.objects.update_or_create(
                    cv_id=issue.id,
                    defaults=issue_data
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                
                # Add to return list (inline values)
                issue_list.append({
                    'id': issue.id,
                    'number': issue.number,
                    'name': issue.name,
                    'date_added': date_added,
                    'store_date': store_date,
                })
            
            logger.info(f"Processed volume {volume_id}: {created_count} created, {updated_count} updated, (total now: {existing_count + created_count})")
            return issue_list
        
        except ServiceError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"API ERROR: issues for volume/{volume_id} - Simyan error: {str(e)} - {response_time_ms}ms")
            return []
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"API ERROR: issues for volume/{volume_id} - Unexpected error: {str(e)} - {response_time_ms}ms")
            return []
