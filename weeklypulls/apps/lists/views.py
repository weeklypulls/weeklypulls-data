from weeklypulls.apps.lists.models import List
from rest_framework import routers, serializers, viewsets


class ListSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = List
        fields = ('id', 'title')


class ListViewSet(viewsets.ModelViewSet):
    queryset = List.objects.all()
    serializer_class = ListSerializer


router = routers.DefaultRouter()
router.register(r'lists', ListViewSet)
