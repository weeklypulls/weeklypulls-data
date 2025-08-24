from django.http import Http404
import logging
from django.db.models import Q, F
from django.db.models.functions import Coalesce
from rest_framework.mixins import CreateModelMixin
from rest_framework.request import clone_request
from rest_framework.response import Response
from rest_framework.decorators import action

from weeklypulls.apps.pulls.models import Pull, MUPull
from weeklypulls.apps.comicvine.models import ComicVineIssue, ComicVineVolume
from rest_framework import routers, serializers, viewsets, status
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, timedelta
from weeklypulls.apps.comicvine.services import ComicVineService
from django.utils import timezone

from weeklypulls.apps.base.filters import IsOwnerFilterBackend
from weeklypulls.apps.pull_lists.models import PullList
from weeklypulls.apps.pulls.permissions import IsPullListOwner
from weeklypulls.settings.pagination import StandardResultsPagination

try:
    import django_filters  # type: ignore
except Exception:  # pragma: no cover - optional in dev before deps installed
    django_filters = None  # type: ignore

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


logger = logging.getLogger(__name__)


class PullSerializer(serializers.HyperlinkedModelSerializer):
    pull_list_id = serializers.PrimaryKeyRelatedField(
        source="pull_list", queryset=PullList.objects.all()
    )
    series_title = serializers.SerializerMethodField()
    series_start_year = serializers.SerializerMethodField()

    def get_series_title(self, obj):
        from weeklypulls.apps.comicvine.models import ComicVineVolume

        volume = (
            ComicVineVolume.objects.filter(cv_id=obj.series_id).only("name").first()
        )
        return getattr(volume, "name", None)

    def get_series_start_year(self, obj):
        from weeklypulls.apps.comicvine.models import ComicVineVolume

        volume = (
            ComicVineVolume.objects.filter(cv_id=obj.series_id)
            .only("start_year")
            .first()
        )
        return getattr(volume, "start_year", None)

    class Meta:
        model = Pull
        fields = (
            "id",
            "series_id",
            "read",
            "pull_list_id",
            "series_title",
            "series_start_year",
        )


class PublisherSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()


class IssueVolumeSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField(required=False, allow_null=True)
    start_year = serializers.IntegerField(required=False, allow_null=True)
    publisher = PublisherSerializer(required=False, allow_null=True)


class PullContextSerializer(serializers.Serializer):
    id = serializers.CharField()
    pulled = serializers.BooleanField()
    read = serializers.BooleanField()
    pull_list_id = serializers.CharField(required=False, allow_null=True)


class IIssueSerializer(serializers.Serializer):
    id = serializers.CharField()
    number = serializers.CharField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_null=True)
    title = serializers.CharField()
    date = serializers.DateField(required=False, allow_null=True)
    images = serializers.ListField(child=serializers.CharField())
    site_url = serializers.CharField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_null=True)
    volume = IssueVolumeSerializer()
    pull = PullContextSerializer(required=False, allow_null=True)


class WeekSerializer(serializers.Serializer):
    week_of = serializers.DateField()
    comics = IIssueSerializer(many=True)


"""Common helpers for issue querying / serialization"""

# For now, only send the original image URL to the frontend
IMAGE_FIELD_CANDIDATES = ("image_original_url",)

# Minimal fields required for unread issues endpoint (with volume context)
ISSUE_BASE_ONLY_FIELDS = (
    "cv_id",
    "name",
    "number",
    "date",
    "description",
    *IMAGE_FIELD_CANDIDATES,
    "volume__cv_id",
    "volume__name",
    "volume__start_year",
    # publisher fields when available
    "volume__publisher__cv_id",
    "volume__publisher__name",
)


def with_issue_image_annotation(qs):
    """Annotate a queryset with a unified image_url using first non-null candidate."""
    return qs.annotate(image_url=Coalesce(*[F(f) for f in IMAGE_FIELD_CANDIDATES]))


ALLOWED_UNREAD_ORDERINGS = {
    # Canonical date only; 'date' = ascending, '-date' = descending
    "date": ("date",),
    "-date": ("-date",),
}


def _images_from_issue(issue):
    """Return a single-element list with the original image URL when available."""
    original = getattr(issue, "image_original_url", None)
    return [original] if original else []


def issue_to_iissue(issue, pull=None):
    """Map ComicVineIssue (+ optional Pull) to IIssue-shaped dict."""
    vol = getattr(issue, "volume", None)
    vol_name = getattr(vol, "name", "")
    number = getattr(issue, "number", None)
    title = (
        f"{vol_name} #{number}".strip()
        if vol_name or number
        else (getattr(issue, "name", None) or "")
    )

    volume_payload = {
        "id": str(getattr(vol, "cv_id", "")),
        "name": getattr(vol, "name", None),
        "start_year": getattr(vol, "start_year", None),
    }
    publisher = getattr(vol, "publisher", None)
    if publisher:
        volume_payload["publisher"] = {
            "id": str(getattr(publisher, "cv_id", "")),
            "name": getattr(publisher, "name", None),
        }

    pull_payload = None
    if pull is not None:
        read_set = set(pull.read or [])
        pull_payload = {
            "id": str(pull.id),
            "pulled": True,
            "read": int(getattr(issue, "cv_id", 0)) in read_set,
            "pull_list_id": (
                str(getattr(pull, "pull_list_id", ""))
                if getattr(pull, "pull_list_id", None)
                else None
            ),
        }

    return {
        "id": str(getattr(issue, "cv_id", "")),
        "number": getattr(issue, "number", None),
        "name": getattr(issue, "name", None),
        "title": title,
        "date": getattr(issue, "date", None),
        "images": _images_from_issue(issue),
        "site_url": getattr(issue, "site_url", None),
        "description": getattr(issue, "description", None),
        "volume": volume_payload,
        "pull": pull_payload,
    }


class PullViewSet(viewsets.ModelViewSet):
    queryset = Pull.objects.all()
    serializer_class = PullSerializer

    owner_lookup_field = "pull_list__owner"

    permission_classes = (IsPullListOwner,)
    filter_backends = (IsOwnerFilterBackend,)

    def create(self, request, *args, **kwargs):
        """overridden to allow for bulk-creation."""
        is_multiple = isinstance(request.data, list)
        serializer = self.get_serializer(data=request.data, many=is_multiple)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_create(self, serializer):
        """Ensure owner is set for new Pulls and support bulk create."""
        # When many=True, DRF's ListSerializer doesn't forward **kwargs to child.create,
        # so we need to handle creation manually to set owner.
        validated = serializer.validated_data
        if isinstance(validated, list):
            objs = []
            for attrs in validated:
                # attrs is a dict with keys like 'pull_list', 'series_id', 'read'
                obj = Pull.objects.create(owner=self.request.user, **attrs)
                objs.append(obj)
            serializer.instance = objs
        else:
            serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        """Mark a single issue id as read for this pull."""
        pull = self.get_object()
        try:
            issue_id = int(request.data.get("issue_id"))
        except (TypeError, ValueError):
            return Response(
                {"detail": "issue_id required"}, status=status.HTTP_400_BAD_REQUEST
            )
        current = set(pull.read or [])
        if issue_id not in current:
            current.add(issue_id)
            pull.read = list(current)
            pull.save(update_fields=["read"])
        serializer = self.get_serializer(pull)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def unread_issues(self, request):
        """
            Return all unread issues for the authenticated user's pull lists.

            This endpoint finds all ComicVine issues that:
            1. Belong to series in the user's pull lists
            2. Are not in the 'read' array of the corresponding Pull
        3. Are ordered by date (newest first)
        """
        # Get user's pull lists with prefetch for efficiency
        user_pulls = (
            Pull.objects.filter(pull_list__owner=request.user)
            .select_related("pull_list")
            .only("id", "series_id", "read", "pull_list_id", "pull_list__owner")
        )

        if not user_pulls.exists():
            # Return empty paginated envelope for consistency with DRF pagination responses
            return Response(
                {"count": 0, "next": None, "previous": None, "results": []},
                status=status.HTTP_200_OK,
            )

        # Build query for unread issues more efficiently
        unread_conditions = Q()

        # Map each series to the user's pull that has the FEWEST read issues so links go to
        # the pull that actually has unread items when duplicates exist across pull lists.
        series_to_pull = {}

        for pull in user_pulls:
            # Prefer the pull with the fewest reads for this series
            rc = len(pull.read or [])
            prev = series_to_pull.get(pull.series_id)
            if prev is None or rc < prev[0]:
                series_to_pull[pull.series_id] = (rc, pull.id)
            # For each pull, find issues in that series that aren't read
            series_condition = Q(volume__cv_id=pull.series_id)

            # Exclude issues that are in the read array
            if pull.read:
                series_condition &= ~Q(cv_id__in=pull.read)

            unread_conditions |= series_condition

        # Determine ordering preference (default: newest date first)
        ordering_param = request.query_params.get("ordering")
        order_tuple = ALLOWED_UNREAD_ORDERINGS.get(ordering_param or "date", ("-date",))

        base_qs = ComicVineIssue.objects.filter(unread_conditions).select_related(
            "volume",
            "volume__publisher",
        )
        unread_issues = with_issue_image_annotation(base_qs).only(
            *ISSUE_BASE_ONLY_FIELDS, "site_url"
        )
        # Apply django-filter (since/series_id) and ordering
        filterset = IssueFilter(request.GET, queryset=unread_issues)
        qs = filterset.qs.order_by(*order_tuple)
        # Paginate using DRF paginator (envelope: count/next/previous/results)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request)

        # Build IIssue-shaped results with minimal pull context (unread => read: False)
        pulls_by_id = {p.id: p for p in user_pulls}
        results = []
        for issue in page:
            series_id = getattr(getattr(issue, "volume", None), "cv_id", None)
            pull_tuple = series_to_pull.get(series_id)
            selected_pull = pulls_by_id.get(pull_tuple[1]) if pull_tuple else None
            # For unread endpoint, we can pass the Pull for context or minimal context if not found
            payload = issue_to_iissue(issue, pull=selected_pull)
            if payload.get("pull") is None and pull_tuple:
                payload["pull"] = {
                    "id": str(pull_tuple[1]),
                    "pulled": True,
                    "read": False,
                }
            results.append(payload)

        return paginator.get_paginated_response(results)


class WeeksViewSet(viewsets.ViewSet):
    def retrieve(self, request, pk=None):
        # Expect pk as YYYY-MM-DD; compute Monday-Sunday range for that week
        req_id = request.META.get("HTTP_X_REQUEST_ID")
        logger.info("WeeksViewSet.retrieve start week=%s req_id=%s", pk, req_id)
        try:
            target_date = datetime.strptime(pk, "%Y-%m-%d").date()
        except Exception:
            logger.warning(
                "WeeksViewSet.retrieve invalid date pk=%s req_id=%s", pk, req_id
            )
            return Response(
                {"detail": "Invalid date. Expected YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ISO weekday: Monday=1..Sunday=7
        days_from_monday = target_date.isoweekday() - 1
        start_date = target_date - timedelta(days=days_from_monday)
        end_date = start_date + timedelta(days=6)

        # Optionally prime from API (default: on) to ensure uncached issues are present
        prime = request.query_params.get("prime", "true").lower() != "false"
        if prime:
            # Use a lightweight week cache to avoid repeated primes within the TTL
            from weeklypulls.apps.comicvine.models import ComicVineWeek

            week_key = start_date  # Monday
            week_cache = ComicVineWeek.objects.filter(week_start=week_key).first()

            # Prime if there's no cache, the cache is expired, a previous failure, or priming hasn't completed yet
            should_prime = (
                not week_cache
                or week_cache.is_cache_expired()
                or week_cache.api_fetch_failed
                or not getattr(week_cache, "priming_complete", False)
            )

            logger.info(
                "WeeksViewSet.retrieve prime check week=%s should_prime=%s has_cache=%s req_id=%s",
                week_key,
                should_prime,
                bool(week_cache),
                req_id,
            )

            if should_prime:
                try:
                    # Use resume markers if present
                    resume_date = getattr(week_cache, "next_date_to_prime", None)
                    resume_page = getattr(week_cache, "current_day_page", 1) or 1
                    summary = ComicVineService().prime_issues_for_date_range(
                        start_date,
                        end_date,
                        start_page=resume_page,
                        resume_date=resume_date,
                    )
                    logger.info(
                        "WeeksViewSet.retrieve primed week=%s summary=%s req_id=%s",
                        week_key,
                        summary,
                        req_id,
                    )
                    # Mark or update cache entry; use shorter TTL when incomplete to retry soon
                    if not week_cache:
                        week_cache = ComicVineWeek(week_start=week_key)
                    complete = bool(summary.get("complete", False))
                    week_cache.priming_complete = complete
                    week_cache.reset_api_failure()
                    # Persist resume markers when not complete
                    if not complete:
                        week_cache.next_date_to_prime = summary.get("next_date")
                        week_cache.current_day_page = int(summary.get("next_page", 1))
                    else:
                        week_cache.next_date_to_prime = None
                        week_cache.current_day_page = 0
                    if complete:
                        week_cache.cache_expires = timezone.now() + timedelta(days=7)
                    else:
                        week_cache.cache_expires = timezone.now() + timedelta(
                            seconds=60
                        )
                    week_cache.save()
                except Exception:
                    # Non-fatal; still try to serve from DB and mark failure
                    logger.exception(
                        "WeeksViewSet.retrieve prime error week=%s req_id=%s",
                        week_key,
                        req_id,
                    )
                    if not week_cache:
                        week_cache = ComicVineWeek(week_start=week_key)
                    # Ensure cache_expires has a value to satisfy NOT NULL
                    if not getattr(week_cache, "cache_expires", None):
                        week_cache.cache_expires = timezone.now() + timedelta(minutes=5)
                    week_cache.mark_api_failure()
                    week_cache.save()

        # Discovery mode: return ALL issues in the Monday–Sunday range (inclusive)
        base_week_qs = ComicVineIssue.objects.filter(
            date__gte=start_date, date__lte=end_date
        ).select_related("volume", "volume__publisher")
        week_qs = with_issue_image_annotation(base_week_qs).only(
            *ISSUE_BASE_ONLY_FIELDS, "site_url"
        )
        # Ordering: date alias maps to canonical date
        ordering_param = request.query_params.get("ordering") or "date"
        if ordering_param == "-date":
            order_tuple = ("-date", "-volume__name", "-number")
        else:
            order_tuple = ("date", "volume__name", "number")
        week_qs = week_qs.order_by(*order_tuple)
        # Limit results to keep payloads reasonable
        try:
            limit = int(request.query_params.get("limit", "1000"))
        except Exception:
            limit = 1000
        limit = max(1, min(2000, limit))
        issues = week_qs[:limit]
        try:
            issues_count = issues.count()
        except Exception:
            issues_count = -1
        logger.info(
            "WeeksViewSet.retrieve query week=%s..%s count=%s req_id=%s",
            start_date,
            end_date,
            issues_count,
            req_id,
        )

        # Build mapping of series -> user's Pull (preferring the one with fewest reads if duplicates exist)
        user_pulls = (
            Pull.objects.filter(pull_list__owner=request.user)
            .only("id", "series_id", "read", "pull_list_id", "pull_list__owner")
            .select_related("pull_list")
        )
        series_to_pull = {}
        for pull in user_pulls:
            rc = len(pull.read or [])
            prev = series_to_pull.get(pull.series_id)
            if prev is None or rc < prev[0]:
                series_to_pull[pull.series_id] = (rc, pull)

        comics = []
        try:
            for issue in issues:
                # Choose appropriate pull (if any) for this series
                series_id = getattr(getattr(issue, "volume", None), "cv_id", None)
                pull_tuple = series_to_pull.get(series_id)
                pull = pull_tuple[1] if pull_tuple else None
                payload = issue_to_iissue(issue, pull=pull)
                comics.append(payload)
        except Exception:
            logger.exception(
                "WeeksViewSet.retrieve build payload error week=%s..%s req_id=%s",
                start_date,
                end_date,
                req_id,
            )
            raise

        serializer = WeekSerializer({"week_of": start_date, "comics": comics})
        return Response(serializer.data, status=status.HTTP_200_OK)


class SeriesSerializer(serializers.Serializer):
    series_id = serializers.CharField()
    title = serializers.CharField()
    comics = IIssueSerializer(many=True)


class SeriesViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated,)

    def retrieve(self, request, pk=None):
        """Return ComicVine volume details and issues for a given series (volume cv_id)."""
        try:
            volume = ComicVineVolume.objects.get(cv_id=int(pk))
        except (ComicVineVolume.DoesNotExist, ValueError):
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Fetch issues for this volume with standard sort/filter
        base_series_qs = ComicVineIssue.objects.filter(volume__cv_id=volume.cv_id)
        series_qs = with_issue_image_annotation(base_series_qs).only(
            *ISSUE_BASE_ONLY_FIELDS, "site_url"
        )
        # Filters: since
        try:
            since = request.query_params.get("since")
            if since:
                series_qs = series_qs.filter(date__gte=since)
        except Exception:
            pass
        # Ordering
        ordering_param = request.query_params.get("ordering") or "date"
        if ordering_param == "-date":
            order_tuple = ("-date", "-number")
        else:
            order_tuple = ("date", "number")
        series_qs = series_qs.order_by(*order_tuple)
        # Limit
        try:
            limit = int(request.query_params.get("limit", "1000"))
        except Exception:
            limit = 1000
        limit = max(1, min(2000, limit))
        issues = series_qs[:limit]

        comics = [issue_to_iissue(issue) for issue in issues]

        series_payload = {
            "series_id": str(volume.cv_id),
            "title": (
                volume.name
                if not getattr(volume, "start_year", None)
                else f"{volume.name}"
            ),
            "comics": comics,
        }
        serializer = SeriesSerializer(series_payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MUPullSerializer(serializers.HyperlinkedModelSerializer):
    pull_list_id = serializers.PrimaryKeyRelatedField(
        source="pull_list", queryset=PullList.objects.all()
    )

    class Meta:
        model = MUPull
        fields = (
            "id",
            "series_id",
            "pull_list_id",
        )


class MUPullViewSet(viewsets.ModelViewSet, CreateModelMixin):
    queryset = MUPull.objects.all()
    serializer_class = MUPullSerializer

    owner_lookup_field = "pull_list__owner"

    permission_classes = (IsPullListOwner,)
    filter_backends = (IsOwnerFilterBackend,)

    def create(self, request, *args, **kwargs):
        """overridden to allow for bulk-creation."""
        is_multiple = isinstance(request.data, list)
        serializer = self.get_serializer(data=request.data, many=is_multiple)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


router = routers.DefaultRouter()
router.register(r"pulls", PullViewSet)
router.register(r"mupulls", MUPullViewSet)
# Register new weeks and series routes
router.register(r"weeks", WeeksViewSet, basename="weeks")
router.register(r"series", SeriesViewSet, basename="series")
