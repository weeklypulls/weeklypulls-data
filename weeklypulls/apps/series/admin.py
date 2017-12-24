from django.contrib import admin
from weeklypulls.apps.series.models import Series


class SeriesAdmin(admin.ModelAdmin):
    fields = ('series_id', 'read', 'pull_list', )
    ordering = ('series_id', )


admin.site.register(Series, SeriesAdmin)
