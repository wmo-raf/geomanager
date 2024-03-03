# Generated by Django 4.2.10 on 2024-02-29 07:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('geomanager', '0045_additionalmapboundarydata_active_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='colorvalue',
            name='show_on_legend',
            field=models.BooleanField(default=True, verbose_name='Show label on Legend'),
        ),
        migrations.AddField(
            model_name='rasterstyle',
            name='legend_type',
            field=models.CharField(choices=[('basic', 'Basic'), ('choropleth', 'Choropleth'), ('gradient', 'Gradient')], default='choropleth', max_length=100, verbose_name='Legend Type'),
        ),
    ]