# Generated by Django 4.2.1 on 2023-05-16 12:05

from django.db import migrations, models
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        ('layermanager', '0003_alter_metadata_cautions_alter_metadata_citation_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='title',
            field=models.CharField(help_text='Title of the category', max_length=16, verbose_name='title'),
        ),
        migrations.AlterField(
            model_name='metadata',
            name='download_data',
            field=models.URLField(blank=True, help_text='External link to where the source data can be found and downloaded', null=True, verbose_name='Data download link'),
        ),
        migrations.AlterField(
            model_name='metadata',
            name='frequency_of_update',
            field=models.CharField(blank=True, help_text='How frequent is the dataset updated. For example daily, weekly, monthly etc', max_length=255, null=True, verbose_name='Frequency of updates'),
        ),
        migrations.AlterField(
            model_name='metadata',
            name='function',
            field=models.TextField(blank=True, help_text='Short summary of what the dataset shows. Keep it short.', max_length=255, null=True, verbose_name='Dataset summary'),
        ),
        migrations.AlterField(
            model_name='metadata',
            name='geographic_coverage',
            field=models.CharField(blank=True, help_text='The geographic coverage of the dataset. For example East Africa or specific country name like Ethiopia, or Africa', max_length=255, null=True, verbose_name='Geographic coverage'),
        ),
        migrations.AlterField(
            model_name='metadata',
            name='learn_more',
            field=models.URLField(blank=True, help_text='External link to where more detail about the dataset can be found', null=True, verbose_name='Learn more link'),
        ),
        migrations.AlterField(
            model_name='metadata',
            name='overview',
            field=wagtail.fields.RichTextField(blank=True, help_text='Detail description of the dataset, including the methodology, references or any other relevant information', null=True, verbose_name='detail'),
        ),
        migrations.AlterField(
            model_name='metadata',
            name='subtitle',
            field=models.CharField(blank=True, help_text='Subtitle if any', max_length=255, null=True, verbose_name='subtitle'),
        ),
        migrations.AlterField(
            model_name='metadata',
            name='title',
            field=models.CharField(help_text='Title of the dataset', max_length=255, verbose_name='title'),
        ),
    ]