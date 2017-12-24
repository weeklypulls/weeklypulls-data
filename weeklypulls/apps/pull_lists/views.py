from weeklypulls.apps.pull_lists.models import PullList
from rest_framework import routers, serializers, viewsets


class PullListSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = PullList
        fields = ('id', 'title')


class PullListViewSet(viewsets.ModelViewSet):
    queryset = PullList.objects.all()
    serializer_class = PullListSerializer


router = routers.DefaultRouter()
router.register(r'pull-lists', PullListViewSet)
