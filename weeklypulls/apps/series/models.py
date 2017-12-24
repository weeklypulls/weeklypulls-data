from django.contrib.postgres.fields import ArrayField
from django.db import models

from weeklypulls.apps.base.models import AbstractBaseModel


class Series(AbstractBaseModel):
    read = ArrayField(models.IntegerField(), default=list)
    series_id = models.IntegerField()
    skipped = ArrayField(models.IntegerField(), default=list)

    class Meta:
        verbose_name_plural = "series"

    def __str__(self):
        return 'Series {}'.format(self.series_id)
