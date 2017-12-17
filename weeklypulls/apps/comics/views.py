import os

from django.http import JsonResponse

import marvelous

from weeklypulls.apps.marvel.models import DjangoCache


def comic_week(request, week_of):
    public_key = os.environ['MAPI_PUBLIC_KEY']
    private_key = os.environ['MAPI_PRIVATE_KEY']
    cache = DjangoCache()
    marvel_api = marvelous.api(public_key, private_key, cache=cache)
    comics = marvel_api.comics({
        'format': "comic",
        'formatType': "comic",
        'noVariants': True,
        'dateRange': "{day},{day}".format(day=week_of),
        'limit': 100
    })

    response = {
        'week_of': week_of,
        'comics': [],
    }

    for comic in comics:
        response['comics'].append({
            'id': comic.id,
            'title': comic.title,
            'on_sale': comic.dates.on_sale,
            'series_id': comic.series.id,
            'images': comic.images,
        })

    return JsonResponse(response)
