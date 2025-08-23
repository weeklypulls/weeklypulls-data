from django.db import migrations, models
from django.db.models import F
from django.db.models.functions import Coalesce


def backfill_issue_date(apps, schema_editor):
    ComicVineIssue = apps.get_model("comicvine", "ComicVineIssue")
    # Single SQL update using COALESCE for efficiency
    ComicVineIssue.objects.update(date=Coalesce(F("store_date"), F("cover_date")))


class Migration(migrations.Migration):
    dependencies = [
        ("comicvine", "0007_rename_cache_week_to_week"),
    ]

    operations = [
        migrations.AddField(
            model_name="comicvineissue",
            name="date",
            field=models.DateField(null=True, blank=True),
        ),
        migrations.RunPython(backfill_issue_date, migrations.RunPython.noop),
    ]
