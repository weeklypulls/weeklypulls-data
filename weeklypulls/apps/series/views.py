from weeklypulls.apps.series.models import Series
from rest_framework import routers, serializers, viewsets


class SeriesSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Series
        fields = ('id', 'series_id', 'read', 'skipped')


class SeriesViewSet(viewsets.ModelViewSet):
    queryset = Series.objects.all()
    serializer_class = SeriesSerializer


router = routers.DefaultRouter()
router.register(r'series', SeriesViewSet)
