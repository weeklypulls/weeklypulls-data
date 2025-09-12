from django.db import migrations, models
import django.db.models.deletion


def purge_volumes_without_publisher(apps, schema_editor):
    ComicVineVolume = apps.get_model("comicvine", "ComicVineVolume")
    ComicVineVolume.objects.filter(publisher__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("comicvine", "0010_remove_comicvineissue_cover_date_and_more"),
    ]

    operations = [
        migrations.RunPython(
            purge_volumes_without_publisher, migrations.RunPython.noop
        ),
        migrations.AlterField(
            model_name="comicvinevolume",
            name="publisher",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="volumes",
                to="comicvine.comicvinepublisher",
            ),
        ),
    ]
