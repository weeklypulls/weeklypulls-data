from django.db.models.fields import CharField

from weeklypulls.apps.base.models import AbstractBaseModel


class PullList(AbstractBaseModel):
    title = CharField(max_length=280)

    class Meta:
        verbose_name_plural = "pull lists"

    def __str__(self):
        return 'Pull List {}'.format(self.title)
