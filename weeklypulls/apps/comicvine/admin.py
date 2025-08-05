from django.contrib import admin
from django.utils.html import format_html
from .models import ComicVineVolume, ComicVineIssue


@admin.register(ComicVineVolume)
class ComicVineVolumeAdmin(admin.ModelAdmin):
    list_display = ('cv_id', 'name', 'start_year', 'count_of_issues', 'last_updated', 'is_cache_expired', 'api_fetch_failed')
    list_filter = ('api_fetch_failed', 'start_year')
    search_fields = ('name', 'cv_id')
    readonly_fields = ('last_updated', 'api_fetch_failure_count', 'api_last_failure')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('cv_id', 'name', 'start_year', 'count_of_issues')
        }),
        ('Cache Status', {
            'fields': ('last_updated', 'cache_expires', 'api_fetch_failed', 'api_fetch_failure_count', 'api_last_failure')
        })
    )
    
    def is_cache_expired(self, obj):
        return obj.is_cache_expired()
    is_cache_expired.boolean = True
    is_cache_expired.short_description = 'Cache Expired'


@admin.register(ComicVineIssue)
class ComicVineIssueAdmin(admin.ModelAdmin):
    list_display = ('cv_id', 'issue_display', 'volume_name', 'number', 'store_date', 'cover_date', 'last_updated', 'is_cache_expired')
    list_filter = ('store_date', 'cover_date', 'volume__start_year', 'api_fetch_failed')
    search_fields = ('name', 'cv_id', 'volume__name', 'number', 'description')
    readonly_fields = ('last_updated', 'api_fetch_failure_count', 'api_last_failure', 'cover_image')
    raw_id_fields = ('volume',)
    date_hierarchy = 'store_date'
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('cv_id', 'name', 'number', 'volume')
        }),
        ('Dates', {
            'fields': ('store_date', 'cover_date', 'date_added', 'date_last_updated')
        }),
        ('Content', {
            'fields': ('description', 'summary', 'aliases')
        }),
        ('Images', {
            'fields': ('cover_image', 'image_medium_url', 'image_small_url', 'image_thumbnail_url')
        }),
        ('URLs', {
            'fields': ('api_url', 'site_url')
        }),
        ('Cache Status', {
            'fields': ('last_updated', 'cache_expires', 'api_fetch_failed', 'api_fetch_failure_count', 'api_last_failure')
        })
    )
    
    def volume_name(self, obj):
        return f"{obj.volume.name} ({obj.volume.start_year})" if obj.volume.start_year else obj.volume.name
    volume_name.short_description = 'Volume'
    volume_name.admin_order_field = 'volume__name'
    
    def issue_display(self, obj):
        number_str = f"#{obj.number}" if obj.number else "No #"
        name_str = f": {obj.name}" if obj.name else ""
        return f"{number_str}{name_str}"
    issue_display.short_description = 'Issue'
    
    def is_cache_expired(self, obj):
        return obj.is_cache_expired()
    is_cache_expired.boolean = True
    is_cache_expired.short_description = 'Cache Expired'
    
    def cover_image(self, obj):
        if obj.image_medium_url:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 150px;" />',
                obj.image_medium_url
            )
        return "No image"
    cover_image.short_description = 'Cover Image'
