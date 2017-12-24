from django.db.models.fields import CharField

from weeklypulls.apps.base.models import AbstractBaseModel


class List(AbstractBaseModel):
    title = CharField(max_length=280)

    class Meta:
        verbose_name_plural = "lists"

    def __str__(self):
        return 'List {}'.format(self.title)
