from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("comicvine", "0011_make_publisher_required_and_cleanup"),
    ]

    operations = [
        # Make week_start no longer the primary key and enforce uniqueness
        migrations.AlterField(
            model_name="comicvineweek",
            name="week_start",
            field=models.DateField(unique=True),
        ),
        # Introduce a surrogate primary key
        migrations.AddField(
            model_name="comicvineweek",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
