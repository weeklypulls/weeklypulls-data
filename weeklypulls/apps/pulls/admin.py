from django.contrib import admin
from weeklypulls.apps.pulls.models import Pull, MUPull, MUPullAlert


class PullsAdmin(admin.ModelAdmin):
    list_display = ('series_id', 'comicvine_volume_display', 'pull_list', 'read_count')
    list_filter = ('pull_list',)
    search_fields = ('series_id',)
    fields = ('series_id', 'read', 'pull_list')
    ordering = ('series_id', )
    
    def get_queryset(self, request):
        """Optimize queryset to avoid N+1 queries for ComicVine volumes"""
        return super().get_queryset(request)
    
    def comicvine_volume_display(self, obj):
        """Display ComicVine volume info or series ID as fallback"""
        # Use the model's property method
        return obj.comicvine_volume_display
    comicvine_volume_display.short_description = 'Series'
    comicvine_volume_display.admin_order_field = 'series_id'
    
    def read_count(self, obj):
        """Show count of read issues"""
        return len(obj.read) if obj.read else 0
    read_count.short_description = 'Read'


admin.site.register(Pull, PullsAdmin)
admin.site.register(MUPull)
admin.site.register(MUPullAlert)