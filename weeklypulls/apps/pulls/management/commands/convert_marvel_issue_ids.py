"""
Management command to convert Marvel issue IDs to ComicVine issue IDs
based on read count heuristic (assumes first N issues were read)
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from weeklypulls.apps.pulls.models import Pull
from weeklypulls.apps.comicvine.services import ComicVineService


class Command(BaseCommand):
    help = 'Convert Marvel issue IDs to ComicVine issue IDs based on read count'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be converted without making changes',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Limit number of series to process (default: 10)',
        )
        parser.add_argument(
            '--series-id',
            type=int,
            help='Process only a specific series ID',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        specific_series = options['series_id']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        cv_service = ComicVineService()
        processed_count = 0
        
        # Get all pulls with read issues
        pulls_query = Pull.objects.filter(read__len__gt=0)
        
        if specific_series:
            pulls_query = pulls_query.filter(series_id=specific_series)
            limit = 1  # Process just this one series
        
        # Group by series_id to get unique series
        series_with_reads = pulls_query.values_list('series_id', flat=True).distinct()
        
        self.stdout.write(f"Found {len(series_with_reads)} series with read issues")
        
        for series_id in series_with_reads[:limit]:
            if self.process_series(cv_service, series_id, dry_run):
                processed_count += 1
            
            # Break early if we hit API limits
            if processed_count >= limit:
                break
        
        self.stdout.write(
            self.style.SUCCESS(f'Processed {processed_count} series')
        )

    def process_series(self, cv_service, series_id, dry_run):
        """Process a single series"""
        try:
            # Get all pulls for this series
            pulls = Pull.objects.filter(series_id=series_id, read__len__gt=0)
            
            if not pulls:
                return False
            
            # Calculate total unique read issues across all pulls for this series
            all_read_issues = set()
            for pull in pulls:
                all_read_issues.update(pull.read)
            
            read_count = len(all_read_issues)
            
            self.stdout.write(f"Series {series_id}: {read_count} unique read issues across {pulls.count()} pulls")
            
            if read_count == 0:
                return False
            
            # Get ComicVine issues for this volume
            issues = cv_service.get_volume_issues(series_id, limit=read_count)
            
            if not issues:
                self.stdout.write(
                    self.style.ERROR(f"  Failed to fetch issues for series {series_id}")
                )
                return False
            
            if len(issues) < read_count:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Only found {len(issues)} issues, but {read_count} were read. "
                        f"Using available issues."
                    )
                )
            
            # Get the first N issue IDs (sorted by issue number)
            comicvine_issue_ids = [issue['id'] for issue in issues[:read_count]]
            
            self.stdout.write(f"  Converting to ComicVine issues: {comicvine_issue_ids[:5]}{'...' if len(comicvine_issue_ids) > 5 else ''}")
            
            if not dry_run:
                # Update all pulls for this series
                with transaction.atomic():
                    for pull in pulls:
                        pull.read = comicvine_issue_ids
                        pull.save(update_fields=['read'])
                
                self.stdout.write(
                    self.style.SUCCESS(f"  Updated {pulls.count()} pulls for series {series_id}")
                )
            else:
                self.stdout.write(f"  Would update {pulls.count()} pulls (DRY RUN)")
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"  Error processing series {series_id}: {str(e)}")
            )
            return False
