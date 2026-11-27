from django.contrib.postgres.fields import ArrayField
from django.db import models

from django.conf import settings
from weeklypulls.apps.base.models import AbstractBaseModel
from weeklypulls.apps.pull_lists.models import PullList


class Pull(AbstractBaseModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pulls",
        null=True,  # temporarily nullable; migration will backfill then set non-null
        blank=True,
    )
    pull_list = models.ForeignKey(PullList, on_delete=models.CASCADE)
    series_id = models.IntegerField()
    read = ArrayField(models.IntegerField(), default=list)

    class Meta:
        verbose_name_plural = "pulls"
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "series_id"], name="uniq_pull_owner_series"
            )
        ]

    def __str__(self):
        return "Pull for {}".format(self.series_id)

    def get_comicvine_volume_info(self):
        """Get ComicVine volume information if cached"""
        try:
            from weeklypulls.apps.comicvine.models import ComicVineVolume

            volume = ComicVineVolume.objects.get(cv_id=self.series_id)
            return (
                f"{volume.name} ({volume.start_year})"
                if volume.start_year
                else volume.name
            )
        except ComicVineVolume.DoesNotExist:
            return None

    @property
    def comicvine_volume_display(self):
        """Display ComicVine volume info or series ID as fallback"""
        cv_info = self.get_comicvine_volume_info()
        return cv_info if cv_info else f"Series {self.series_id}"
