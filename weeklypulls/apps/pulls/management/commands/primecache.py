import time
import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from weeklypulls.apps.comicvine.models import ComicVineVolume, ComicVineIssue
from weeklypulls.apps.comicvine.services import ComicVineService
from weeklypulls.apps.pulls.models import Pull

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fetch missing or expired ComicVine data within API limits (replaces Marvel API cache priming)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=180,
            help='Maximum API requests to make (default: 180)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fetched without making API calls'
        )
        parser.add_argument(
            '--force-volumes',
            action='store_true',
            help='Include volumes that have failed API calls recently'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        dry_run = options['dry_run']
        force_volumes = options['force_volumes']
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN - No API calls will be made"))
        
        self.stdout.write(f"Starting ComicVine data fetch with limit of {limit} API requests...")
        
        service = ComicVineService()
        requests_made = 0
        
        # Priority 1: Fetch missing volumes (volumes referenced by Pulls but not cached)
        missing_volumes = self._get_missing_volumes()
        self.stdout.write(f"Found {len(missing_volumes)} missing volumes")
        
        for volume_id in missing_volumes:
            if requests_made >= limit:
                break
                
            if dry_run:
                self.stdout.write(f"Would fetch volume {volume_id}")
                requests_made += 1  # Count the request that would be made
            else:
                try:
                    volume = service.get_volume(volume_id, force_refresh=force_volumes)
                    if volume:
                        self.stdout.write(f"✅ Fetched volume {volume_id}: {volume.name}")
                    requests_made += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Failed to fetch volume {volume_id}: {e}")
                    )
                    requests_made += 1
            
            # Rate limiting safety
            if not dry_run:
                time.sleep(0.5)  # Extra safety beyond Simyan's rate limiting
        
        # Priority 2: Refresh expired volumes
        expired_volumes = self._get_expired_volumes(force_volumes)
        self.stdout.write(f"Found {len(expired_volumes)} expired volumes (smart refresh: recent series weekly, older series monthly)")
        
        for volume in expired_volumes:
            if requests_made >= limit:
                break
                
            if dry_run:
                age_info = f" (started {volume.start_year})" if volume.start_year else ""
                self.stdout.write(f"Would refresh volume {volume.cv_id}: {volume.name}{age_info}")
                requests_made += 1  # Count the request that would be made
            else:
                try:
                    refreshed = service.get_volume(volume.cv_id, force_refresh=True)
                    if refreshed:
                        age_info = f" (started {volume.start_year})" if volume.start_year else ""
                        self.stdout.write(f"🔄 Refreshed volume {volume.cv_id}: {volume.name}{age_info}")
                    requests_made += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Failed to refresh volume {volume.cv_id}: {e}")
                    )
                    requests_made += 1
            
            if not dry_run:
                time.sleep(0.5)
        
        # Priority 3: Fetch issues for volumes that need them
        remaining_requests = limit - requests_made
        volumes_needing_issues = self._get_volumes_needing_issues(max_volumes=remaining_requests)
        self.stdout.write(f"Found {len(volumes_needing_issues)} volumes needing issue data (prioritizing recent series, limited by {remaining_requests} remaining requests)")
        
        for volume in volumes_needing_issues:
            if requests_made >= limit:
                break
                
            if dry_run:
                age_info = f" (started {volume.start_year})" if volume.start_year else ""
                self.stdout.write(f"Would fetch issues for volume {volume.cv_id}: {volume.name}{age_info}")
                requests_made += 1  # Count the request that would be made
            else:
                try:
                    # Fetch 500 issues for the volume
                    issues = service.get_volume_issues(volume.cv_id)
                    age_info = f" (started {volume.start_year})" if volume.start_year else ""
                    self.stdout.write(f"📚 Fetched {len(issues)} issues for {volume.name}{age_info}")
                    requests_made += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Failed to fetch issues for volume {volume.cv_id}: {e}")
                    )
                    requests_made += 1
            
            if not dry_run:
                time.sleep(0.5)
        
        # Summary
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"DRY RUN complete. Would have made ~{requests_made} API requests")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"ComicVine fetch complete. Made {requests_made} API requests (limit: {limit})")
            )

    def _get_missing_volumes(self):
        """Get volume IDs referenced by Pulls but not in ComicVineVolume table"""
        # Get all series_ids from Pulls (now that conversion is complete, all should be ComicVine IDs)
        referenced_volumes = Pull.objects.values_list('series_id', flat=True).distinct()
        
        # Find which ones we don't have cached
        cached_volumes = ComicVineVolume.objects.filter(
            cv_id__in=referenced_volumes
        ).values_list('cv_id', flat=True)
        
        missing = set(referenced_volumes) - set(cached_volumes)
        return list(missing)

    def _get_expired_volumes(self, force_failed=False):
        """Get ComicVineVolume objects that need refreshing with smart prioritization"""
        now = timezone.now()
        
        # Base query: expired volumes
        query = Q(cache_expires__lt=now)
        
        if not force_failed:
            # Skip volumes that have failed recently unless forced
            recent_failure_cutoff = now - timedelta(hours=24)
            query &= Q(
                Q(api_fetch_failed=False) | 
                Q(api_last_failure__lt=recent_failure_cutoff)
            )
        
        # Smart refresh logic based on series age and activity
        current_year = now.year
        
        # Priority 1: Recent series (last 3 years) - refresh if older than 1 week
        recent_cutoff = now - timedelta(days=7)
        recent_series = Q(start_year__gte=current_year - 3) & Q(last_updated__lt=recent_cutoff)
        
        # Priority 2: Older series (4-10 years old) - refresh if older than 2 weeks  
        older_cutoff = now - timedelta(days=14)
        older_series = Q(start_year__gte=current_year - 10, start_year__lt=current_year - 3) & Q(last_updated__lt=older_cutoff)
        
        # Priority 3: Very old series (10+ years old) - refresh if older than 1 month
        very_old_cutoff = now - timedelta(days=30)
        very_old_series = Q(start_year__lt=current_year - 10) & Q(last_updated__lt=very_old_cutoff)
        
        # Get recent series first (most likely to have new issues)
        recent_volumes = list(ComicVineVolume.objects.filter(
            query & recent_series
        ).order_by('-start_year', 'last_updated')[:10])
        
        # Fill remaining slots with older series if we have space
        remaining_slots = 20 - len(recent_volumes)
        if remaining_slots > 0:
            older_volumes = list(ComicVineVolume.objects.filter(
                query & (older_series | very_old_series)
            ).order_by('last_updated')[:remaining_slots])
            recent_volumes.extend(older_volumes)
        
        return recent_volumes

    def _get_volumes_needing_issues(self, max_volumes=None):
        """Get volumes that exist but don't have issue data cached, prioritized by activity"""
        now = timezone.now()
        current_year = now.year
        
        # If no max_volumes specified, use a reasonable default
        if max_volumes is None:
            max_volumes = 10
        
        # Don't go crazy - cap at a reasonable number even with high API limits
        max_volumes = min(max_volumes, 50)
        
        # Get volumes that have pulls but no cached issues
        volumes_with_pulls = ComicVineVolume.objects.filter(
            cv_id__in=Pull.objects.values_list('series_id', flat=True).distinct()
        )
        
        # Prioritize recent series that are more likely to be actively read
        volumes_without_issues = []
        
        # Priority 1: Recent series (last 5 years) - likely active
        recent_volumes = volumes_with_pulls.filter(
            start_year__gte=current_year - 5
        ).order_by('-start_year')
        
        for volume in recent_volumes:
            if len(volumes_without_issues) >= max_volumes:
                break

            # Check if volume has no issues OR fewer than the records indicate
            issue_count = ComicVineIssue.objects.filter(volume=volume).count()
            if issue_count == 0 or issue_count < volume.count_of_issues:
                volumes_without_issues.append(volume)
        
        # Priority 2: Fill remaining spots with older series if needed
        if len(volumes_without_issues) < max_volumes:
            older_volumes = volumes_with_pulls.filter(
                start_year__lt=current_year - 5
            ).order_by('-start_year')  # More recent of the older ones first
            
            for volume in older_volumes:
                if len(volumes_without_issues) >= max_volumes:
                    break
                # Check if volume has no issues OR has fewer than 50 (indicating incomplete fetch)
                issue_count = ComicVineIssue.objects.filter(volume=volume).count()
                if issue_count == 0 or (issue_count % 50 == 0 and issue_count > 0):
                    # Either no issues, or a multiple of 50 (might be incomplete)
                    volumes_without_issues.append(volume)
        
        return volumes_without_issues
