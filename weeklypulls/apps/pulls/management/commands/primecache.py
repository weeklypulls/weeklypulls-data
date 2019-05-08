from datetime import datetime
from time import sleep

import arrow
import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand, CommandError
from django.core.validators import URLValidator
from requests.exceptions import ConnectionError

from weeklypulls.apps.pulls.models import Pull, MUPull


class Command(BaseCommand):
    help = "Prime Marvel API cache for known series"

    def handle(self, *args, **options):
        try:
            start_marker = datetime.now()
            # validate it's a good url
            URLValidator()(settings.MAPI_URL)
            # get all known series
            series_ids = set(
                list(Pull.objects.order_by('series_id').distinct('series_id')
                     .values_list('series_id', flat=True)) +
                list(MUPull.objects.order_by('series_id').distinct('series_id')
                     .values_list('series_id', flat=True))
            )
            # ping the api
            for series_id in series_ids:
                requests.get(f'{settings.MAPI_URL}/series/{series_id}')
                sleep(0.01)  # be gentle

            # prime the week
            start, end = arrow.utcnow().span('week')
            requests.get(f'{settings.MAPI_URL}/weeks/{start:%Y-%m-%d}')

            self.stdout.write(f'Cache primed in {datetime.now() - start_marker}')
        except AttributeError:
            raise CommandError('Please add MAPI_URL to your settings.')
        except ValidationError:
            raise CommandError(f'Invalid MAPI_URL: {settings.MAPI_URL}')
        except ConnectionError as conn_error:
            raise CommandError(f'Invalid MAPI_URL: {conn_error.args}')
