import json
from django.db import models
from datetime import timedelta
from django.utils import timezone
from random import randint


class ApiCache(models.Model):
    key = models.TextField(primary_key=True)
    value = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class DjangoCache():
    def get(self, key):
        try:
            cache_entry = ApiCache.objects.get(key=key)
            random_day_ago = timezone.now() - timedelta(days=randint(4, 10))

            if cache_entry.created_at < random_day_ago:
                print('Deleting old cache entry', key)
                cache_entry.delete()
                return None

            print('Returning cache entry', key)
            return json.loads(cache_entry.value)
        except:
            return None

    def store(self, key, value):
        print('Storing cache entry', key)
        ApiCache.objects.create(key=key, value=json.dumps(value))
        return value
