from weeklypulls.apps.pulls.models import Pull
from rest_framework import routers, serializers, viewsets

from weeklypulls.apps.base.filters import IsOwnerFilterBackend
from weeklypulls.apps.pull_lists.models import PullList
from weeklypulls.apps.pulls.permissions import IsPullListOwner


class PullSerializer(serializers.HyperlinkedModelSerializer):
    pull_list_id = serializers.PrimaryKeyRelatedField(
        source='pull_list', queryset=PullList.objects.all())

    class Meta:
        model = Pull
        fields = ('id', 'series_id', 'read', 'skipped', 'pull_list_id', )


class PullViewSet(viewsets.ModelViewSet):
    queryset = Pull.objects.all()
    serializer_class = PullSerializer

    permission_classes = (IsPullListOwner, )
    filter_backends = (IsOwnerFilterBackend, )


router = routers.DefaultRouter()
router.register(r'pulls', PullViewSet)
