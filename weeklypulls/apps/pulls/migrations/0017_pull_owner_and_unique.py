from django.db import migrations, models
from django.conf import settings


def backfill_owner(apps, schema_editor):
    Pull = apps.get_model("pulls", "Pull")
    db_alias = schema_editor.connection.alias
    # backfill owner_id from pull_list.owner_id
    for p in Pull.objects.using(db_alias).select_related("pull_list__owner").all():
        if getattr(p, "owner_id", None) is None:
            p.owner_id = p.pull_list.owner_id
            p.save(update_fields=["owner_id"])


def dedupe_pulls(apps, schema_editor):
    """Merge duplicate Pulls per (owner, series_id) by keeping the one with the most reads."""
    Pull = apps.get_model("pulls", "Pull")
    db_alias = schema_editor.connection.alias
    from collections import defaultdict

    groups = defaultdict(list)
    for p in Pull.objects.using(db_alias).only("id", "owner_id", "series_id", "read"):
        if p.owner_id is None:
            continue
        groups[(p.owner_id, p.series_id)].append(p)

    for (_owner_id, _series_id), pulls in groups.items():
        if len(pulls) <= 1:
            continue
        pulls.sort(key=lambda x: (-len(x.read or []), str(x.id)))
        keep = pulls[0]
        keep_set = set(keep.read or [])
        for p in pulls[1:]:
            keep_set.update(p.read or [])
        if list(keep_set) != (keep.read or []):
            keep.read = list(keep_set)
            keep.save(update_fields=["read"])
        for p in pulls[1:]:
            p.delete()


class Migration(migrations.Migration):
    # Run operations in separate transactions to avoid "pending trigger events"
    atomic = False

    dependencies = [
        ("pulls", "0016_remove_pull_migrated_to_comicvine"),
        ("pull_lists", "0005_pulllist_mu_enabled"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="pull",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="pulls",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_owner, migrations.RunPython.noop),
        migrations.RunPython(dedupe_pulls, migrations.RunPython.noop),
        # Owner remains nullable in this step; NOT NULL and UNIQUE come in 0018
    ]
