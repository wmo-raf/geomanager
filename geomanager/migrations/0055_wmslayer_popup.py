from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('geomanager', '0054_vectortilelayer_is_pmtiles'),
    ]

    operations = [
        migrations.AddField(
            model_name='wmslayer',
            name='popup',
            field=models.BooleanField(default=False, help_text='If checked, a popup will be displayed when clicking on the layer.', verbose_name='Enable popup'),
        ),
    ]
