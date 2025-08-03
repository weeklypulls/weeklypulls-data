import time
import logging
from datetime import timedelta
from typing import Optional
from django.conf import settings
from django.utils import timezone

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
            
            volume.name = cv_volume.name or f"Volume {volume_id}"
            volume.start_year = cv_volume.start_year
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

    def get_volume_issues(self, volume_id: int, limit: int = 100) -> list:
        """
        Get issues for a volume, sorted by issue number/date, continuing from where we left off.
        Also saves the issues to the database.
        
        Args:
            volume_id: ComicVine volume ID
            limit: Maximum number of issues to fetch
            
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

            # Check how many issues we already have to determine offset
            existing_count = ComicVineIssue.objects.filter(volume=volume).count()
            
            logger.info(f"Fetching issues for volume {volume_id} (already have {existing_count}, getting next {limit})")
            start_time = time.time()
            
            # Get issues for the volume using Simyan's list_issues method
            # Filter by volume and sort by issue number to get chronological order
            issues = self.cv.list_issues(
                params={
                    'filter': f'volume:{volume_id}',
                    'sort': 'store_date:asc'  # Use store_date instead of issue_number
                },
                max_results=limit,
                offset=existing_count  # Start from where we left off
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"API SUCCESS: issues for volume/{volume_id} - {len(issues)} issues - {response_time_ms}ms")
            
            # Convert to simple list of dicts AND save to database
            issue_list = []
            created_count = 0
            updated_count = 0
            
            for issue in issues:
                # Parse dates
                store_date = None
                cover_date = None
                date_added = None
                date_last_updated = None
                
                if hasattr(issue, 'store_date') and issue.store_date:
                    try:
                        from dateutil.parser import parse
                        store_date = parse(issue.store_date).date()
                    except:
                        pass
                        
                if hasattr(issue, 'cover_date') and issue.cover_date:
                    try:
                        from dateutil.parser import parse
                        cover_date = parse(issue.cover_date).date()
                    except:
                        pass
                        
                if hasattr(issue, 'date_added') and issue.date_added:
                    try:
                        from dateutil.parser import parse
                        date_added = parse(issue.date_added)
                    except:
                        pass
                        
                if hasattr(issue, 'date_last_updated') and issue.date_last_updated:
                    try:
                        from dateutil.parser import parse
                        date_last_updated = parse(issue.date_last_updated)
                    except:
                        pass
                
                # Create or update ComicVineIssue record
                from django.utils import timezone
                cache_expiry = timezone.now() + timedelta(days=30)  # Issues don't change often
                
                issue_data = {
                    'name': getattr(issue, 'name', None),
                    'number': getattr(issue, 'number', None),
                    'volume': volume,
                    'store_date': store_date,
                    'cover_date': cover_date,
                    'description': getattr(issue, 'description', None),
                    'date_added': date_added,
                    'date_last_updated': date_last_updated,
                    'api_url': getattr(issue, 'api_detail_url', None),
                    'site_url': getattr(issue, 'site_detail_url', None),
                    'cache_expires': cache_expiry,
                }
                
                comic_issue, created = ComicVineIssue.objects.update_or_create(
                    cv_id=issue.id,
                    defaults=issue_data
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                
                # Add to return list
                issue_list.append({
                    'id': issue.id,
                    'number': getattr(issue, 'number', None),
                    'name': getattr(issue, 'name', None),
                    'date_added': getattr(issue, 'date_added', None),
                    'store_date': getattr(issue, 'store_date', None),
                })
            
            logger.info(f"Saved {len(issues)} issues for volume {volume_id}: {created_count} created, {updated_count} updated (total: {existing_count + len(issues)})")
            return issue_list
            
        except ServiceError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"API ERROR: issues for volume/{volume_id} - Simyan error: {str(e)} - {response_time_ms}ms")
            return []
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"API ERROR: issues for volume/{volume_id} - Unexpected error: {str(e)} - {response_time_ms}ms")
            return []
