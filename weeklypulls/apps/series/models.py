from django.db import models
from django.contrib.postgres.fields import ArrayField


class Series(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    read = ArrayField(models.IntegerField(), default=list)
    series_id = models.IntegerField(unique=True)
    skipped = ArrayField(models.IntegerField(), default=list)

    class Meta:
        verbose_name_plural = "series"

    def __str__(self):
        return 'Series {}'.format(self.series_id)
