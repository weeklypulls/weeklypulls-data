import arrow
from rest_framework import routers, serializers, viewsets

from weeklypulls.apps.base.filters import IsOwnerFilterBackend
from weeklypulls.apps.pull_lists.models import PullList
from weeklypulls.apps.pull_lists.permissions import IsOwner
from weeklypulls.apps.pulls.models import MUPullAlert


class PullListSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")

    class Meta:
        model = PullList
        fields = (
            "id",
            "title",
            "owner",
        )


class PullListViewSet(viewsets.ModelViewSet):
    queryset = PullList.objects.all()
    serializer_class = PullListSerializer

    owner_lookup_field = "owner"

    permission_classes = (IsOwner,)
    filter_backends = (IsOwnerFilterBackend,)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


router = routers.DefaultRouter()
router.register(r"pull-lists", PullListViewSet)


def get_weekly_mu_alerts_for_list(pull_list: PullList):
    """
    Find all alerts that should fire today for a given list.
    Not a user-facing view but still a view from a conceptual perspective.

    :param pull_list PullList instance
    :return list of MUPullAlert
    """
    if not pull_list.mu_enabled:
        return []

    start, end = arrow.utcnow().span("week")

    return MUPullAlert.objects.filter(
        series_id__in=pull_list.mupull_set.values_list("series_id", flat=True),
        alert_date__range=(start.date(), end.date()),
    )
