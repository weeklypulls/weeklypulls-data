import os

from django.db import models
from django.contrib.postgres.fields import ArrayField

import marvelous

from weeklypulls.apps.marvel.models import DjangoCache


class Series(models.Model):
    series_id = models.IntegerField(unique=True)
    read = ArrayField(models.IntegerField(), default=list)
    skipped = ArrayField(models.IntegerField(), default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "series"

    def __str__(self):
        try:
            return '{} ({})'.format(self.api['title'], self.series_id)
        except Exception:
            return 'Series {} (api error)'.format(self.series_id)

    @property
    def api(self):
        public_key = os.environ['MAPI_PUBLIC_KEY']
        private_key = os.environ['MAPI_PRIVATE_KEY']
        cache = DjangoCache()
        marvel_api = marvelous.api(public_key, private_key, cache=cache)
        series = marvel_api.series(self.series_id)

        response = {
            'title': series.title,
            'comics': [],
            'series_id': self.series_id,
        }

        series_args = {
            'format': "comic",
            'formatType': "comic",
            'noVariants': True,
            'limit': 100,
        }

        for comic in series.comics(series_args):
            response['comics'].append({
                'id': comic.id,
                'title': comic.title,
                'read': (comic.id in self.read),
                'skipped': (comic.id in self.skipped),
                'on_sale': comic.dates.on_sale,
                'series_id': comic.series.id,
                'images': comic.images,
            })

        return response
