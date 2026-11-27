from rest_framework import routers, serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from weeklypulls.apps.base.filters import IsOwnerFilterBackend
from weeklypulls.apps.pull_lists.models import PullList
from weeklypulls.apps.pull_lists.permissions import IsOwner


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

    permission_classes = (IsAuthenticated, IsOwner)
    filter_backends = (IsOwnerFilterBackend,)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


router = routers.DefaultRouter()
router.register(r"pull-lists", PullListViewSet)
