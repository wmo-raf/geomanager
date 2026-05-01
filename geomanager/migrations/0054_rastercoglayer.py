from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields
import uuid
import wagtail.blocks
import wagtail.fields
import wagtail.images.blocks


class Migration(migrations.Migration):

    dependencies = [
        ('geomanager', '0053_wmslayer_legend_from_capabilities'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='layer_type',
            field=models.CharField(
                choices=[
                    ('raster_file', 'Raster File - NetCDF/GeoTiff'),
                    ('vector_file', 'Vector File - Shapefile, Geojson'),
                    ('wms', 'Web Map Service - WMS Layer'),
                    ('raster_tile', 'XYZ Raster Tile Layer'),
                    ('vector_tile', 'XYZ Vector Tile Layer'),
                    ('raster_cog', 'Raster COG - Cloud Optimized GeoTIFF (remote URL)'),
                ],
                default='raster_file',
                max_length=100,
                verbose_name='Layer type',
            ),
        ),
        migrations.CreateModel(
            name='RasterCOGLayer',
            fields=[
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(help_text='Layer title', max_length=255, verbose_name='title')),
                ('default', models.BooleanField(default=False, help_text='Is Default Layer', verbose_name='default')),
                ('order', models.IntegerField(blank=True, editable=False, null=True)),
                ('url_template', models.CharField(
                    help_text='URL template with a time placeholder. Supported placeholders: '
                              '{time:strftime} (e.g. {time:%Y}, {time:%Y-%m-%d}), {year}, {month}, {day}, {hour}. '
                              'Example: https://example.org/data/file_{time:%Y}.tif',
                    max_length=2048,
                    verbose_name='COG URL template',
                )),
                ('time_start', models.DateTimeField(
                    help_text='First timestamp of the series (inclusive)',
                    verbose_name='Start time',
                )),
                ('time_end', models.DateTimeField(
                    help_text='Last timestamp of the series (inclusive)',
                    verbose_name='End time',
                )),
                ('time_step_value', models.PositiveIntegerField(default=1, verbose_name='Time step value')),
                ('time_step_unit', models.CharField(
                    choices=[
                        ('years', 'Years'),
                        ('months', 'Months'),
                        ('days', 'Days'),
                        ('hours', 'Hours'),
                    ],
                    default='years',
                    max_length=20,
                    verbose_name='Time step unit',
                )),
                ('date_format', models.CharField(
                    blank=True,
                    choices=[
                        ('yyyy-MM-dd HH:mm', 'Hour minute:second - (E.g 2023-01-01 00:00)'),
                        ('yyyy-MM-dd', 'Day - (E.g 2023-01-01)'),
                        ('pentadal', 'Pentadal - (E.g Jan 2023 - P1 1-5th)'),
                        ('dekadal', 'Dekadal - (E.g Jan 2023 - D1 1-10th)'),
                        ('yyyy-MM', 'Month number - (E.g 2023-01)'),
                        ('MMMM yyyy', 'Month name - (E.g January 2023)'),
                        ('yyyy', 'Year - (E.g 2023)'),
                    ],
                    default='yyyy-MM-dd HH:mm',
                    max_length=100,
                    null=True,
                    verbose_name='Display Format for DateTime Selector',
                )),
                ('use_custom_legend', models.BooleanField(default=False, verbose_name='Use custom legend')),
                ('legend', wagtail.fields.StreamField(
                    [
                        ('legend', wagtail.blocks.StructBlock([
                            ('type', wagtail.blocks.ChoiceBlock(choices=[
                                ('basic', 'Basic'),
                                ('gradient', 'Gradient'),
                                ('choropleth', 'Choropleth'),
                            ], label='Legend Type')),
                            ('items', wagtail.blocks.ListBlock(wagtail.blocks.StructBlock([
                                ('value', wagtail.blocks.CharBlock(
                                    help_text="Can be a number or text e.g '10' or '10-20' or 'Vegetation'",
                                    label='value',
                                )),
                                ('color', wagtail.blocks.CharBlock(
                                    help_text='Color value e.g rgb(73,73,73) or #494949',
                                    label='color',
                                )),
                            ]), label='Legend Items', min_num=1)),
                        ], label='Custom Legend')),
                        ('legend_image', wagtail.images.blocks.ImageChooserBlock(label='Custom Image')),
                    ],
                    blank=True,
                    null=True,
                    use_json_field=True,
                    verbose_name='Legend',
                )),
                ('dataset', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='raster_cog_layers',
                    to='geomanager.dataset',
                    verbose_name='dataset',
                )),
                ('style', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='geomanager.rasterstyle',
                    verbose_name='style',
                )),
            ],
            options={
                'verbose_name': 'Raster COG Layer',
                'verbose_name_plural': 'Raster COG Layers',
                'ordering': ['order'],
            },
        ),
    ]
