from django.contrib import admin
from weeklypulls.apps.pull_lists.models import PullList


class PullListsAdmin(admin.ModelAdmin):
    fields = ('title', )
    ordering = ('title',)


admin.site.register(PullList, PullListsAdmin)
