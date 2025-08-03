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
        self.stdout.write(f"Found {len(expired_volumes)} expired volumes")
        
        for volume in expired_volumes:
            if requests_made >= limit:
                break
                
            if dry_run:
                self.stdout.write(f"Would refresh volume {volume.cv_id}: {volume.name}")
            else:
                try:
                    refreshed = service.get_volume(volume.cv_id, force_refresh=True)
                    if refreshed:
                        self.stdout.write(f"🔄 Refreshed volume {volume.cv_id}: {volume.name}")
                    requests_made += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Failed to refresh volume {volume.cv_id}: {e}")
                    )
                    requests_made += 1
            
            if not dry_run:
                time.sleep(0.5)
        
        # Priority 3: Fetch issues for volumes that need them
        volumes_needing_issues = self._get_volumes_needing_issues()
        self.stdout.write(f"Found {len(volumes_needing_issues)} volumes needing issue data")
        
        for volume in volumes_needing_issues:
            if requests_made >= limit:
                break
                
            if dry_run:
                self.stdout.write(f"Would fetch issues for volume {volume.cv_id}: {volume.name}")
            else:
                try:
                    # Fetch up to 50 issues per volume to stay within limits
                    issues = service.get_volume_issues(volume.cv_id, limit=50)
                    self.stdout.write(f"📚 Fetched {len(issues)} issues for {volume.name}")
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
        """Get ComicVineVolume objects that need refreshing"""
        now = timezone.now()
        
        query = Q(cache_expires__lt=now)
        
        if not force_failed:
            # Skip volumes that have failed recently unless forced
            recent_failure_cutoff = now - timedelta(hours=24)
            query &= Q(
                Q(api_fetch_failed=False) | 
                Q(api_last_failure__lt=recent_failure_cutoff)
            )
        
        return ComicVineVolume.objects.filter(query)[:20]  # Limit to 20 volumes per run

    def _get_volumes_needing_issues(self):
        """Get volumes that exist but don't have issue data cached"""
        # Get volumes that have pulls but no cached issues
        volumes_with_pulls = ComicVineVolume.objects.filter(
            cv_id__in=Pull.objects.values_list('series_id', flat=True).distinct()
        )
        
        # For now, just return volumes that have no issues cached
        # In practice, you might want more sophisticated logic
        volumes_without_issues = []
        for volume in volumes_with_pulls[:10]:  # Limit to 10 volumes per run
            if not ComicVineIssue.objects.filter(volume=volume).exists():
                volumes_without_issues.append(volume)
        
        return volumes_without_issues
