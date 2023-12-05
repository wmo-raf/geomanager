# Generated by Django 4.1.10 on 2023-11-30 12:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('geomanager', '0036_vectortilelayer_popup_config_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataset',
            name='enable_all_multi_layers_on_add',
            field=models.BooleanField(default=True, help_text='Enable all Multi-Layers at once when adding the dataset to the map', verbose_name='Enable all Multi-Layers when adding to map'),
        ),
    ]