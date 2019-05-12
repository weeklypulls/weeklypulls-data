from django.http import Http404
from rest_framework.mixins import CreateModelMixin
from rest_framework.request import clone_request
from rest_framework.response import Response

from weeklypulls.apps.pulls.models import Pull, MUPull
from rest_framework import routers, serializers, viewsets, status

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

    owner_lookup_field = 'pull_list__owner'

    permission_classes = (IsPullListOwner, )
    filter_backends = (IsOwnerFilterBackend, )


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


router = routers.DefaultRouter()
router.register(r'pulls', PullViewSet)
router.register(r'mupulls', MUPullViewSet)
