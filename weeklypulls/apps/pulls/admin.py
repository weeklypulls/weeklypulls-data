from django.contrib import admin
from weeklypulls.apps.pulls.models import Pull, MUPull, MUPullAlert


class PullsAdmin(admin.ModelAdmin):
    fields = ('series_id', 'read', 'pull_list', )
    ordering = ('series_id', )


admin.site.register(Pull, PullsAdmin)
admin.site.register(MUPull)
admin.site.register(MUPullAlert)