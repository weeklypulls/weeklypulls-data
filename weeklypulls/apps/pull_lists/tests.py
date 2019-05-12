import arrow
from django.contrib.auth.models import User
from django.test import TestCase

from weeklypulls.apps.pull_lists.models import PullList
from weeklypulls.apps.pull_lists.views import get_weekly_mu_alerts_for_list
from weeklypulls.apps.pulls.models import MUPull, MUPullAlert


class MUAlertsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        # IDs don't really matter in this context, using random ones
        cls.series_1 = 23012
        cls.series_2 = 23013

        cls.test_user = User.objects.create(username='testuser')
        cls.pull_list = PullList.objects.create(title=f"{__name__} test list",
                                                owner=cls.test_user,
                                                mu_enabled=True)
        MUPull.objects.create(series_id=cls.series_1,
                              pull_list=cls.pull_list)
        MUPull.objects.create(series_id=cls.series_2,
                              pull_list=cls.pull_list)

    def test_weekly_view_correct(self):
        self.assertTrue(self.pull_list.mupull_set.all().count() == 2)

        issue_ok = 1
        issue_fail = 2

        six_months_ago = arrow.utcnow().shift(months=-6).date()
        alert1 = MUPullAlert.create_for_issue(issue_ok, self.series_1, six_months_ago)
        alert2 = MUPullAlert.create_for_issue(issue_ok, self.series_2, six_months_ago)
        alert3 = MUPullAlert.create_for_issue(issue_fail, self.series_1, six_months_ago.replace(day=+14))

        alerts = get_weekly_mu_alerts_for_list(self.pull_list)
        self.assertIn(alert1, alerts)
        self.assertIn(alert2, alerts)
        self.assertNotIn(alert3, alerts)
