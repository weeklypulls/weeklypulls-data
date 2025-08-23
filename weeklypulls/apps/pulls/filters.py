try:
    import django_filters  # type: ignore
except Exception:  # pragma: no cover - optional in dev before deps installed
    django_filters = None  # type: ignore

from weeklypulls.apps.comicvine.models import ComicVineIssue


if django_filters is not None:

    class IssueFilter(django_filters.FilterSet):
        since = django_filters.DateFilter(field_name="date", lookup_expr="gte")
        series_id = django_filters.NumberFilter(field_name="volume__cv_id")

        class Meta:
            model = ComicVineIssue
            fields = ["since", "series_id"]

else:
    # Fallback no-op filter when django-filter isn't available yet
    class IssueFilter:  # type: ignore
        def __init__(self, _data, queryset):
            self.qs = queryset
