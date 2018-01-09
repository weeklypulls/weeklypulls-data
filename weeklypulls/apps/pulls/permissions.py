from rest_framework import permissions


class IsPullListOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.pull_list.owner == request.user
