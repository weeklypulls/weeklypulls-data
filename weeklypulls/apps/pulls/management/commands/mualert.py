from datetime import datetime, date
import logging
from smtplib import SMTPException

import requests
from django.core.management import BaseCommand
from django.conf import settings

from weeklypulls.apps.pull_lists.models import PullList
from weeklypulls.apps.pulls.models import MUPull, MUPullAlert

logger = logging.getLogger(__name__)


email_template = """
Hey {name},

Great news! The following comics should now be available on Marvel Unlimited!

{comics}

Remember that you can manage your alerts at https://www.weeklypulls.com .

Enjoy!

The WeeklyPulls Team
"""

# annoyingly little details, because more would entail lots of api calls...
comic_template = """{comic[title]}
"""

subject = """New comics on Marvel Universe from your favourite series!"""


class Command(BaseCommand):
    help = "Send alerts for MUPulls"

    def handle(self, *args, **options):
        # { User_instance : [comic1, comic2...] }
        alert_map = {}

        today_alerts = MUPullAlert.objects.filter(alert_date__exact=date.today())
        for alert in today_alerts:
            # this should eventually be parallelised, I think
            # get the comic details
            api_response = requests.get(f"{settings.MAPI_URL}/comics/{alert.issue_id}")
            details = api_response.json()
            if not details:
                logger.error(f"Issue {alert.issue_id} could not be retrieved from MAPI")
                continue

            # find pull_lists that include this series
            for pl in PullList.objects.filter(mupull__series_id=alert.series_id):
                comic_list = alert_map.get(pl.owner, [])
                comic_list.append(details)
                alert_map[pl.owner] = comic_list

        for user in alert_map:
            try:
                comics = ""
                for comic in alert_map[user]:
                    comics += comic_template.format(comic=comic)
                name = (
                    user.get_full_name() or user.get_short_name() or user.get_username()
                )
                message = email_template.format(name=name, comics=comics)
                # choose one:
                # user.email_user() - I/O inefficient (one smtp conn per email)
                # send_mass_mail() - memory inefficient (gotta store all messages in memory)
                user.email_user(subject, message, fail_silently=False)
            except SMTPException as e:
                logger.error(f"Error sending email to {user.email}: {e}")
