from django.http import Http404
from django.db.models import Q
from django.db.models.functions import Coalesce
from rest_framework.mixins import CreateModelMixin
from rest_framework.request import clone_request
from rest_framework.response import Response
from rest_framework.decorators import action

from weeklypulls.apps.pulls.models import Pull, MUPull
from weeklypulls.apps.comicvine.models import ComicVineIssue, ComicVineVolume
from rest_framework import routers, serializers, viewsets, status
from rest_framework.permissions import IsAuthenticated

from weeklypulls.apps.base.filters import IsOwnerFilterBackend
from weeklypulls.apps.pull_lists.models import PullList
from weeklypulls.apps.pulls.permissions import IsPullListOwner


class PullSerializer(serializers.HyperlinkedModelSerializer):
    pull_list_id = serializers.PrimaryKeyRelatedField(
        source='pull_list', queryset=PullList.objects.all())

    class Meta:
        model = Pull
        fields = ('id', 'series_id', 'read', 'pull_list_id', )


class UnreadIssueSerializer(serializers.ModelSerializer):
    """Serializer for unread ComicVine issues"""
    volume_name = serializers.CharField(source='volume.name', read_only=True)
    volume_start_year = serializers.IntegerField(source='volume.start_year', read_only=True)
    volume_id = serializers.IntegerField(source='volume.cv_id', read_only=True)
    pull_id = serializers.SerializerMethodField()
    image_url = serializers.CharField(read_only=True)

    def get_pull_id(self, obj):
        mapping = self.context.get('series_to_pull', {}) or {}
        series_id = getattr(getattr(obj, 'volume', None), 'cv_id', None)
        return mapping.get(series_id)
    
    class Meta:
        model = ComicVineIssue
        fields = (
            'cv_id', 'name', 'number', 'store_date', 'cover_date',
            'volume_id', 'volume_name', 'volume_start_year',
            'description', 'image_medium_url', 'image_url', 'site_url', 'pull_id'
        )


# New serializers for Weeks API
class WeekComicSerializer(serializers.Serializer):
    id = serializers.CharField()
    images = serializers.ListField(child=serializers.CharField())
    on_sale = serializers.DateField()
    series_id = serializers.CharField()
    title = serializers.CharField()


class WeekSerializer(serializers.Serializer):
    comics = WeekComicSerializer(many=True)


class PullViewSet(viewsets.ModelViewSet):
    queryset = Pull.objects.all()
    serializer_class = PullSerializer

    owner_lookup_field = 'pull_list__owner'

    permission_classes = (IsPullListOwner, )
    filter_backends = (IsOwnerFilterBackend, )

    def create(self, request, *args, **kwargs):
        """ overridden to allow for bulk-creation. """
        is_multiple = isinstance(request.data, list)
        serializer = self.get_serializer(data=request.data, many=is_multiple)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a single issue id as read for this pull."""
        pull = self.get_object()
        try:
            issue_id = int(request.data.get('issue_id'))
        except (TypeError, ValueError):
            return Response({'detail': 'issue_id required'}, status=status.HTTP_400_BAD_REQUEST)
        current = set(pull.read or [])
        if issue_id not in current:
            current.add(issue_id)
            pull.read = list(current)
            pull.save(update_fields=['read'])
        serializer = self.get_serializer(pull)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def unread_issues(self, request):
        """
        Return all unread issues for the authenticated user's pull lists.
        
        This endpoint finds all ComicVine issues that:
        1. Belong to series in the user's pull lists
        2. Are not in the 'read' array of the corresponding Pull
        3. Are ordered by store_date (newest first)
        """
        # Get user's pull lists with prefetch for efficiency
        user_pulls = Pull.objects.filter(
            pull_list__owner=request.user
        ).select_related('pull_list').only(
            'id', 'series_id', 'read', 'pull_list__owner'
        )
        
        if not user_pulls.exists():
            return Response([], status=status.HTTP_200_OK)
        
        # Build query for unread issues more efficiently
        unread_conditions = Q()
        series_to_pull = {}
        
        for pull in user_pulls:
            # Map series_id to pull.id for serializer context
            series_to_pull[pull.series_id] = pull.id
            # For each pull, find issues in that series that aren't read
            series_condition = Q(volume__cv_id=pull.series_id)
            
            # Exclude issues that are in the read array
            if pull.read:
                series_condition &= ~Q(cv_id__in=pull.read)
            
            unread_conditions |= series_condition
        
        # Query unread issues with optimized fetching
        unread_issues = ComicVineIssue.objects.filter(
            unread_conditions
        ).select_related('volume').only(
            # Only fetch fields we actually need
            'cv_id', 'name', 'number', 'store_date', 'cover_date',
            'description', 'image_medium_url', 'image_super_url', 'image_original_url',
            'image_screen_url', 'image_small_url', 'image_thumbnail_url', 'image_tiny_url', 'image_icon_url',
            'site_url',
            'volume__cv_id', 'volume__name', 'volume__start_year'
        ).annotate(
            image_url=Coalesce(
                'image_medium_url', 'image_super_url', 'image_original_url',
                'image_screen_url', 'image_small_url', 'image_thumbnail_url', 'image_tiny_url', 'image_icon_url'
            )
        ).order_by('-store_date', '-cover_date')
        
        serializer = UnreadIssueSerializer(unread_issues, many=True, context={'series_to_pull': series_to_pull})
        return Response(serializer.data, status=status.HTTP_200_OK)


class WeeksViewSet(viewsets.ViewSet):
    """Return issues for a specific week (store_date) for the authenticated user's pulls."""
    permission_classes = (IsAuthenticated,)

    def retrieve(self, request, pk=None):
        week_date = pk  # Expecting YYYY-MM-DD
        # Pulls for this user
        user_pulls = Pull.objects.filter(
            pull_list__owner=request.user
        ).only('series_id', 'pull_list__owner', 'read')

        series_ids = list(user_pulls.values_list('series_id', flat=True))
        if not series_ids:
            return Response({'comics': []}, status=status.HTTP_200_OK)

        # Issues for that week in user's series
        issues = ComicVineIssue.objects.filter(
            volume__cv_id__in=series_ids,
            store_date=week_date
        ).select_related('volume').only(
            'cv_id', 'name', 'number', 'store_date',
            'image_medium_url', 'image_super_url', 'image_original_url',
            'image_screen_url', 'image_small_url', 'image_thumbnail_url', 'image_tiny_url', 'image_icon_url',
            'volume__cv_id', 'volume__name'
        ).annotate(
            image_url=Coalesce(
                'image_medium_url', 'image_super_url', 'image_original_url',
                'image_screen_url', 'image_small_url', 'image_thumbnail_url', 'image_tiny_url', 'image_icon_url'
            )
        ).order_by('volume__name', 'number')

        comics = []
        # Build a set for quicker read lookup: series_id -> set(read_ids)
        reads_by_series = {}
        for p in user_pulls:
            reads_by_series[str(p.series_id)] = set(p.read or [])

        for issue in issues:
            # Compose a title like "<Volume Name> #<number>"
            vol_name = getattr(issue.volume, 'name', '')
            number = getattr(issue, 'number', '')
            title = f"{vol_name} #{number}".strip()
            image = getattr(issue, 'image_medium_url', None) or getattr(issue, 'image_url', None)
            images = [image] if image else []
            comics.append({
                'id': str(issue.cv_id),
                'images': images,
                'on_sale': issue.store_date,
                'series_id': str(getattr(issue.volume, 'cv_id', '')),
                'title': title,
            })

        serializer = WeekSerializer({'comics': comics})
        return Response(serializer.data, status=status.HTTP_200_OK)


class MUPullSerializer(serializers.HyperlinkedModelSerializer):
    pull_list_id = serializers.PrimaryKeyRelatedField(
        source='pull_list', queryset=PullList.objects.all())

    class Meta:
        model = MUPull
        fields = ('id', 'series_id', 'pull_list_id', )


class MUPullViewSet(viewsets.ModelViewSet, CreateModelMixin):
    queryset = MUPull.objects.all()
    serializer_class = MUPullSerializer

    owner_lookup_field = 'pull_list__owner'

    permission_classes = (IsPullListOwner, )
    filter_backends = (IsOwnerFilterBackend, )

    def create(self, request, *args, **kwargs):
        """ overridden to allow for bulk-creation. """
        is_multiple = isinstance(request.data, list)
        serializer = self.get_serializer(data=request.data, many=is_multiple)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


router = routers.DefaultRouter()
router.register(r'pulls', PullViewSet)
router.register(r'mupulls', MUPullViewSet)
# Register new weeks route
router.register(r'weeks', WeeksViewSet, basename='weeks')
