# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2017-12-24 13:24
from __future__ import unicode_literals

from django.db import migrations, models
import uuid


def create_uuid(apps, schema_editor):
    Pull = apps.get_model('pulls', 'Pull')
    for pull in Pull.objects.all():
        pull.idu = uuid.uuid4()
        pull.save()


class Migration(migrations.Migration):

    dependencies = [
        ('pulls', '0007_auto_20171224_1320'),
    ]

    operations = [
        migrations.RunPython(create_uuid),
        migrations.RemoveField(
            model_name='pull',
            name='id',
        ),
        migrations.AlterField(
            model_name='pull',
            name='idu',
            field=models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False),
        ),
    ]