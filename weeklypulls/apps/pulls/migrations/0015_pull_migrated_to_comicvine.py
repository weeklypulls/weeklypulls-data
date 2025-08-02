# Generated manually - add migrated_to_comicvine field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pulls', '0014_remove_pull_skipped'),
    ]

    operations = [
        migrations.AddField(
            model_name='pull',
            name='migrated_to_comicvine',
            field=models.BooleanField(default=False),
        ),
    ]
