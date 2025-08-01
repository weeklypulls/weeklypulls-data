from django.contrib import admin
from .models import ComicVineVolume


@admin.register(ComicVineVolume)
class ComicVineVolumeAdmin(admin.ModelAdmin):
    list_display = ('cv_id', 'name', 'start_year', 'last_updated', 'is_cache_expired', 'api_fetch_failed')
    list_filter = ('api_fetch_failed', 'start_year')
    search_fields = ('name', 'cv_id')
    readonly_fields = ('last_updated', 'api_fetch_failure_count', 'api_last_failure')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('cv_id', 'name', 'start_year')
        }),
        ('Cache Status', {
            'fields': ('last_updated', 'cache_expires', 'api_fetch_failed', 'api_fetch_failure_count', 'api_last_failure')
        })
    )
    
    def is_cache_expired(self, obj):
        return obj.is_cache_expired()
    is_cache_expired.boolean = True
    is_cache_expired.short_description = 'Cache Expired'
