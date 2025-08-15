from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("pulls", "0017_pull_owner_and_unique"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="pull",
            name="owner",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="pulls",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="pull",
            constraint=models.UniqueConstraint(
                fields=("owner", "series_id"), name="uniq_pull_owner_series"
            ),
        ),
    ]
