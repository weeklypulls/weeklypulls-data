from django.db.models.fields import CharField, BooleanField
from django.db.models import CASCADE, ForeignKey

from weeklypulls.apps.base.models import AbstractBaseModel


class PullList(AbstractBaseModel):
    title = CharField(max_length=280)
    owner = ForeignKey('auth.User', related_name='pull_lists', on_delete=CASCADE)
    mu_enabled = BooleanField(default=False, null=False, blank=False)

    class Meta:
        verbose_name_plural = "pull lists"

    def __str__(self):
        return 'Pull List {}'.format(self.title)
