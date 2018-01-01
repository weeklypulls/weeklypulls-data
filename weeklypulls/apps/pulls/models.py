from django.contrib.postgres.fields import ArrayField
from django.db import models

from weeklypulls.apps.base.models import AbstractBaseModel
from weeklypulls.apps.pull_lists.models import PullList


class Pull(AbstractBaseModel):
    read = ArrayField(models.IntegerField(), default=list)
    series_id = models.IntegerField()
    skipped = ArrayField(models.IntegerField(), default=list)
    pull_list = models.ForeignKey(PullList, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = "pulls"

    def __str__(self):
        return 'Pull for {}'.format(self.series_id)
