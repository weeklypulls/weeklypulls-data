from django.contrib import admin
from weeklypulls.apps.pulls.models import Pull


class PullsAdmin(admin.ModelAdmin):
    fields = ('series_id', 'read', 'pull_list', )
    ordering = ('series_id', )


admin.site.register(Pull, PullsAdmin)
