from django.core.management.base import BaseCommand
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
            help='Cache all volumes from existing pulls (use carefully!)'
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
        
        if options['cache_all_volumes']:
            self.stdout.write("Caching all volumes from existing pulls...")
            
            # Get all unique series IDs from Pull and MUPull (these are now ComicVine volume IDs)
            pull_volumes = set(Pull.objects.values_list('series_id', flat=True))
            mupull_volumes = set(MUPull.objects.values_list('series_id', flat=True))
            all_volumes = pull_volumes.union(mupull_volumes)
            
            self.stdout.write(f"Found {len(all_volumes)} unique volumes to cache")
            
            success_count = 0
            failure_count = 0
            
            for volume_id in sorted(all_volumes):
                self.stdout.write(f"Caching volume {volume_id}...")
                
                try:
                    volume = service.get_volume(volume_id)
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
                    f"  Success: {success_count}\n"
                    f"  Failures: {failure_count}\n"
                    f"  Total: {len(all_volumes)}"
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
        )
