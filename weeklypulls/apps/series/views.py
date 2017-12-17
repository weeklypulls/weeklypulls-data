from weeklypulls.apps.series.models import Series
from rest_framework import routers, serializers, viewsets


class SeriesSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Series
        fields = ('id', 'series_id', 'read', 'skipped', 'api')


class ListSeriesSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Series
        fields = ('id', 'series_id', 'read', 'skipped')


class SeriesViewSet(viewsets.ModelViewSet):
    queryset = Series.objects.all()
    serializer_action_classes = {
        'list': ListSeriesSerializer,
    }

    def get_serializer_class(self):
        try:
            return self.serializer_action_classes[self.action]
        except (KeyError, AttributeError):
            return SeriesSerializer

    serializer_class = SeriesSerializer


router = routers.DefaultRouter()
router.register(r'series', SeriesViewSet)
