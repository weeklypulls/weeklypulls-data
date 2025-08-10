from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User

from rest_framework.mixins import CreateModelMixin
from rest_framework.request import Request


class OwnedMixin(object):
    OWNER_LOOKUP_FIELD_ATTRIBUTE = "owner_lookup_field"

    @staticmethod
    def get_owner_lookup_field(view):
        try:
            owner_lookup_field = getattr(
                view, IsOwnerMixin.OWNER_LOOKUP_FIELD_ATTRIBUTE
            )
        except AttributeError:
            raise AssertionError(
                f"'{IsOwnerMixin.OWNER_LOOKUP_FIELD_ATTRIBUTE}' must be explicitly set in '{view.__class__.__name__}'"
            )

        return owner_lookup_field


class IsOwnerMixin(OwnedMixin):
    @staticmethod
    def get_filter_kwargs(request, owner_lookup_field):
        filter_kwargs = {}

        if owner_lookup_field is not None:
            filter_kwargs[owner_lookup_field] = request.user.id

        return filter_kwargs


class CreateModelWithOwnerMixin(CreateModelMixin):

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
