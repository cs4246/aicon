# Generated by Django 5.1.1 on 2024-09-15 22:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0014_task_gpus'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='submission',
            name='docker',
        ),
        migrations.RemoveField(
            model_name='submission',
            name='metadata',
        ),
        migrations.RemoveField(
            model_name='submission',
            name='runner',
        ),
        migrations.RemoveField(
            model_name='task',
            name='max_image_size',
        ),
    ]
