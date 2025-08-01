from django.contrib import admin
from weeklypulls.apps.pulls.models import Pull, MUPull, MUPullAlert


class PullsAdmin(admin.ModelAdmin):
    list_display = ('series_id', 'comicvine_volume_display', 'pull_list', 'read_count', 'skipped_count')
    list_filter = ('pull_list',)
    search_fields = ('series_id',)
    fields = ('series_id', 'read', 'pull_list', )
    ordering = ('series_id', )
    
    def get_queryset(self, request):
        """Optimize queryset to avoid N+1 queries for ComicVine volumes"""
        queryset = super().get_queryset(request)
        
        # Prefetch ComicVine volumes in a single query
        from weeklypulls.apps.comicvine.models import ComicVineVolume
        
        # Get all unique series_ids from the current page
        series_ids = list(queryset.values_list('series_id', flat=True).distinct())
        
        # Fetch all ComicVine volumes for these series in one query
        volumes = ComicVineVolume.objects.filter(cv_id__in=series_ids)
        volume_lookup = {vol.cv_id: vol for vol in volumes}
        
        # Cache the volumes on each object to avoid individual queries
        pulls = list(queryset)
        for pull in pulls:
            pull._cached_comicvine_volume = volume_lookup.get(pull.series_id)
        
        return pulls
    
    def comicvine_volume_display(self, obj):
        """Display ComicVine volume info or series ID as fallback"""
        # Use cached volume if available
        if hasattr(obj, '_cached_comicvine_volume') and obj._cached_comicvine_volume:
            volume = obj._cached_comicvine_volume
            return f"{volume.name} ({volume.start_year})" if volume.start_year else volume.name
        
        # Fallback to series ID
        return f"Series {obj.series_id}"
    comicvine_volume_display.short_description = 'Series'
    comicvine_volume_display.admin_order_field = 'series_id'
    
    def read_count(self, obj):
        """Show count of read issues"""
        return len(obj.read) if obj.read else 0
    read_count.short_description = 'Read'
    
    def skipped_count(self, obj):
        """Show count of skipped issues"""
        return len(obj.skipped) if obj.skipped else 0
    skipped_count.short_description = 'Skipped'


admin.site.register(Pull, PullsAdmin)
admin.site.register(MUPull)
admin.site.register(MUPullAlert)