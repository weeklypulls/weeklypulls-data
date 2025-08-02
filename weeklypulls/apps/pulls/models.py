import arrow
from django.contrib.postgres.fields import ArrayField
from django.db import models

from weeklypulls.apps.base.models import AbstractBaseModel
from weeklypulls.apps.pull_lists.models import PullList


class Pull(AbstractBaseModel):
    pull_list = models.ForeignKey(PullList, on_delete=models.CASCADE)
    series_id = models.IntegerField()
    read = ArrayField(models.IntegerField(), default=list)
    migrated_to_comicvine = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "pulls"

    def __str__(self):
        return 'Pull for {}'.format(self.series_id)
    
    def get_comicvine_volume_info(self):
        """Get ComicVine volume information if cached"""
        try:
            from weeklypulls.apps.comicvine.models import ComicVineVolume
            volume = ComicVineVolume.objects.get(cv_id=self.series_id)
            return f"{volume.name} ({volume.start_year})" if volume.start_year else volume.name
        except ComicVineVolume.DoesNotExist:
            return None
    
    @property
    def comicvine_volume_display(self):
        """Display ComicVine volume info or series ID as fallback"""
        cv_info = self.get_comicvine_volume_info()
        return cv_info if cv_info else f"Series {self.series_id}"


class MUPull(AbstractBaseModel):
    pull_list = models.ForeignKey(PullList, on_delete=models.CASCADE)
    series_id = models.IntegerField()

    def __str__(self):
        return f'{self.pull_list} / Series {self.series_id} '


class MUPullAlert(AbstractBaseModel):
    series_id = models.IntegerField()
    issue_id = models.IntegerField()
    alert_date = models.DateField()

    def __str__(self):
        return f'Series {self.series_id} / Issue {self.issue_id} / {self.alert_date}'

    @staticmethod
    def create_for_issue(issue_id, series_id, publication_date):
        """
        schedule a MU-related alert for the given issue details
        (i.e. when the issue is supposed to appear on MU, in 6 months).

        :param issue_id: comic ID
        :param series_id: series ID
        :param publication_date: Date/Arrow object or string
        :return: created MUPullAlert
        """
        alert_date = arrow.get(publication_date).replace(months=+6)
        alert = MUPullAlert.objects.create(series_id=series_id,
                                           issue_id=issue_id,
                                           alert_date=alert_date.date())
        return alert
