from rest_framework.filters import BaseFilterBackend
from rest_framework.mixins import ListModelMixin

from weeklypulls.apps.base.api_mixins import IsOwnerMixin


class IsOwnerFilterBackend(IsOwnerMixin, BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        # determine if filtering applies; oversimplified but works for `GenericView`-based views, including ViewSets
        if not isinstance(view, ListModelMixin):
            return queryset

        # type: ignore # see: https://github.com/python/mypy/issues/1996
        owner_lookup_field = self.get_owner_lookup_field(view)

        if owner_lookup_field is None:
            return queryset

        filter_kwargs = self.get_filter_kwargs(request, owner_lookup_field)

        return queryset.filter(**filter_kwargs)
