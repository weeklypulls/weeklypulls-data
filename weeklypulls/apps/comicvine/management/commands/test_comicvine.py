from django.core.management.base import BaseCommand
from django.utils import timezone
from weeklypulls.apps.comicvine.services import ComicVineService
from weeklypulls.apps.pulls.models import Pull, MUPull


class Command(BaseCommand):
    help = "Test ComicVine API and cache volume data for existing pulls"

    def add_arguments(self, parser):
        parser.add_argument(
            '--volume-id', 
            type=int, 
            help='Test with a specific ComicVine volume ID'
        )
        parser.add_argument(
            '--rate-limit-status', 
            action='store_true', 
            help='Show current rate limit status'
        )
        parser.add_argument(
            '--cache-all-volumes', 
            action='store_true', 
            help='Cache all volumes from existing pulls (skips already cached ones)'
        )
        parser.add_argument(
            '--force-refresh-all', 
            action='store_true', 
            help='Force refresh all volumes, ignoring existing cache'
        )

    def handle(self, *args, **options):
        service = ComicVineService()
        
        if options['rate_limit_status']:
            self.stdout.write(
                self.style.WARNING(
                    "Rate limit status is now handled automatically by Simyan.\n"
                    "Use --volume-id to test volume fetching instead."
                )
            )
            return
        
        if options['volume_id']:
            volume_id = options['volume_id']
            self.stdout.write(f"Testing API with volume ID: {volume_id}")
            
            volume = service.get_volume(volume_id)
            if volume:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Successfully fetched: {volume.name} ({volume.start_year})\n"
                        f"  Cache expires: {volume.cache_expires}\n"
                        f"  Failed fetches: {volume.api_fetch_failure_count}"
                    )
                )
            else:
                self.stdout.write(self.style.ERROR(f"✗ Failed to fetch volume {volume_id}"))
            return
        
        if options['cache_all_volumes'] or options['force_refresh_all']:
            action = "force refreshing" if options['force_refresh_all'] else "caching"
            self.stdout.write(f"Starting {action} of all volumes from existing pulls...")
            
            # Get all unique series IDs from Pull and MUPull (these are now ComicVine volume IDs)
            pull_volumes = set(Pull.objects.values_list('series_id', flat=True))
            mupull_volumes = set(MUPull.objects.values_list('series_id', flat=True))
            all_volumes = pull_volumes.union(mupull_volumes)
            
            if options['force_refresh_all']:
                # Force refresh all volumes
                volumes_to_fetch = all_volumes
                already_cached = set()
                self.stdout.write(f"Found {len(all_volumes)} unique volumes to force refresh")
            else:
                # Check which volumes are already cached and fresh
                from weeklypulls.apps.comicvine.models import ComicVineVolume
                already_cached = set(
                    ComicVineVolume.objects.filter(
                        cv_id__in=all_volumes,
                        api_fetch_failed=False
                    ).exclude(
                        cache_expires__lt=timezone.now()  # Exclude expired cache
                    ).values_list('cv_id', flat=True)
                )
                
                volumes_to_fetch = all_volumes - already_cached
                
                self.stdout.write(f"Found {len(all_volumes)} unique volumes total")
                self.stdout.write(f"Already cached (fresh): {len(already_cached)}")
                self.stdout.write(f"Volumes to fetch: {len(volumes_to_fetch)}")
                
                if not volumes_to_fetch:
                    self.stdout.write(self.style.SUCCESS("All volumes are already cached and fresh!"))
                    return
            
            success_count = 0
            failure_count = 0
            
            for volume_id in sorted(volumes_to_fetch):
                self.stdout.write(f"Caching volume {volume_id}...")
                
                try:
                    # Use force_refresh if this is a force refresh operation
                    force_refresh = options['force_refresh_all']
                    volume = service.get_volume(volume_id, force_refresh=force_refresh)
                    if volume and not volume.api_fetch_failed:
                        success_count += 1
                        self.stdout.write(f"  ✓ {volume.name}")
                    else:
                        failure_count += 1
                        self.stdout.write(f"  ✗ Failed to cache volume {volume_id}")
                except Exception as e:
                    failure_count += 1
                    self.stdout.write(f"  ✗ Error caching volume {volume_id}: {e}")
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nCaching complete:\n"
                    f"  Already cached: {len(already_cached)}\n"
                    f"  Newly cached: {success_count}\n"
                    f"  Failures: {failure_count}\n"
                    f"  Total volumes: {len(all_volumes)}"
                )
            )
            return
        
        # Default: show usage
        self.stdout.write(
            "ComicVine API Test Command\n\n"
            "Usage examples:\n"
            "  python manage.py test_comicvine --rate-limit-status\n"
            "  python manage.py test_comicvine --volume-id 123456\n"
            "  python manage.py test_comicvine --cache-all-volumes\n"
            "  python manage.py test_comicvine --force-refresh-all\n"
        )
