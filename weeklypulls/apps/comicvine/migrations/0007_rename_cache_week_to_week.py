from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("comicvine", "0006_add_publisher_model_and_fk"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="ComicVineCacheWeek",
            new_name="ComicVineWeek",
        ),
        migrations.AddField(
            model_name="comicvineweek",
            name="priming_complete",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="comicvineweek",
            name="next_date_to_prime",
            field=models.DateField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="comicvineweek",
            name="current_day_page",
            field=models.IntegerField(default=0),
        ),
    ]
