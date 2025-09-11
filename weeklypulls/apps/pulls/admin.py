from django.contrib import admin
from django.db.models import OuterRef, Subquery
from weeklypulls.apps.pulls.models import Pull, MUPull, MUPullAlert


class PullsAdmin(admin.ModelAdmin):
    list_display = (
        "series_id",
        "comicvine_volume_display",
        "publisher",
        "pull_list",
        "read_count",
    )
    list_filter = ("pull_list",)
    search_fields = ("series_id",)
    fields = ("series_id", "read", "pull_list")
    ordering = ("series_id",)

    def get_queryset(self, request):
        """Optimize queryset to avoid N+1 queries for ComicVine volumes"""
        qs = super().get_queryset(request)
        from weeklypulls.apps.comicvine.models import ComicVineVolume

        return qs.annotate(
            _publisher_name=Subquery(
                ComicVineVolume.objects.filter(cv_id=OuterRef("series_id")).values(
                    "publisher__name"
                )[:1]
            )
        )

    def comicvine_volume_display(self, obj):
        """Display ComicVine volume info or series ID as fallback"""
        # Use the model's property method
        return obj.comicvine_volume_display

    comicvine_volume_display.short_description = "Series"
    comicvine_volume_display.admin_order_field = "series_id"

    def read_count(self, obj):
        """Show count of read issues"""
        return len(obj.read) if obj.read else 0

    read_count.short_description = "Read"

    def publisher(self, obj):
        return getattr(obj, "_publisher_name", None) or "—"

    publisher.short_description = "Publisher"
    publisher.admin_order_field = "_publisher_name"


admin.site.register(Pull, PullsAdmin)
admin.site.register(MUPull)
admin.site.register(MUPullAlert)
