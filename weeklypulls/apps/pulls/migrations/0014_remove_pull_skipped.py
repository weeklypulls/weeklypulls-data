# Generated manually - remove skipped field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pulls", "0013_merge_read_skipped_arrays"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="pull",
            name="skipped",
        ),
    ]
