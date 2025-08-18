from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("comicvine", "0005_add_publisher_to_volume"),
    ]

    # 0005 already created ComicVinePublisher and the ForeignKey on volumes in prod.
    # Leave 0006 as a no-op to align migration history without attempting to re-create anything.
    operations = []
