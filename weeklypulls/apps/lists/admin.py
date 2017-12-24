from django.contrib import admin
from weeklypulls.apps.lists.models import List


class ListsAdmin(admin.ModelAdmin):
    fields = ('title', )
    ordering = ('title',)


admin.site.register(List, ListsAdmin)
