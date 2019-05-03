from datetime import datetime
from time import sleep

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand, CommandError
from django.core.validators import URLValidator
from requests.exceptions import ConnectionError

from weeklypulls.apps.pulls.models import Pull


class Command(BaseCommand):
    help = "Prime Marvel API cache for known series"

    def handle(self, *args, **options):
        try:
            start_marker = datetime.now()
            # validate it's a good url
            URLValidator()(settings.MAPI_URL)
            # get all known series
            series_ids = [record['series_id']
                          for record in Pull.objects.values('series_id').distinct()]
            # ping the api
            for series_id in series_ids:
                requests.get(f'{settings.MAPI_URL}/series/{series_id}')
                sleep(0.01)  # be gentle
            self.stdout.write(f'Cache primed in {datetime.now() - start_marker}')
        except AttributeError:
            raise CommandError('Please add MAPI_URL to your settings.')
        except ValidationError:
            raise CommandError(f'Invalid MAPI_URL: {settings.MAPI_URL}')
        except ConnectionError as conn_error:
            raise CommandError(f'Invalid MAPI_URL: {conn_error.args}')
