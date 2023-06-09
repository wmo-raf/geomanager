import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail import blocks
from wagtail.admin.panels import (
    FieldPanel,
    TabbedInterface,
    ObjectList,
    InlinePanel
)
from wagtail.contrib.modeladmin.helpers import AdminURLHelper
from wagtail.contrib.settings.models import BaseSiteSetting
from wagtail.contrib.settings.registry import register_setting
from wagtail.fields import StreamField, RichTextField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Orderable
from wagtail_adminsortable.models import AdminSortable
from wagtailiconchooser.widgets import IconChooserWidget

from geomanager.helpers import (
    get_layer_action_url,
    get_preview_url,
    get_upload_url
)
from .tile_gl import MBTSource
from ..blocks import NavigationItemsBlock

DEFAULT_RASTER_MAX_UPLOAD_SIZE_MB = 10


class Category(TimeStampedModel, AdminSortable, ClusterableModel):
    title = models.CharField(max_length=16, verbose_name=_("title"), help_text=_("Title of the category"))
    icon = models.CharField(max_length=255, verbose_name=_("icon"), blank=True, null=True)
    active = models.BooleanField(default=True, verbose_name=_("active"), help_text=_("Is the category active ?"))
    public = models.BooleanField(default=True, verbose_name=_("public"), help_text=_("Is the category public ?"))

    class Meta(AdminSortable.Meta):
        verbose_name_plural = _("Categories")

    def __str__(self):
        return self.title

    panels = [
        FieldPanel("title"),
        FieldPanel("icon", widget=IconChooserWidget),
        FieldPanel("active"),
        FieldPanel("public"),

        InlinePanel("sub_categories", heading=_("Sub Categories"), label=_("Sub Category")),
    ]

    def datasets_list_url(self):
        dataset_admin_helper = AdminURLHelper(Dataset)
        dataset_index_url = dataset_admin_helper.get_action_url("index")
        return dataset_index_url + f"?category__id__exact={self.pk}"

    def dataset_create_url(self):
        dataset_admin_helper = AdminURLHelper(Dataset)
        dataset_create_url = dataset_admin_helper.get_action_url("create")
        return dataset_create_url + f"?category_id={self.pk}"


class SubCategory(Orderable):
    category = ParentalKey(Category, on_delete=models.CASCADE, related_name="sub_categories")
    title = models.CharField(max_length=256, verbose_name=_("title"))
    active = models.BooleanField(default=True, verbose_name=_("active"))
    public = models.BooleanField(default=True, verbose_name=_("public"))

    panels = [
        FieldPanel("title"),
        FieldPanel("active"),
        FieldPanel("public"),
    ]

    def __str__(self):
        return self.title


class Dataset(TimeStampedModel):
    DATASET_TYPE_CHOICES = (
        ("file", "Raster"),
        ("wms", "WMS"),
        ("vector", "Vector"),
    )

    CURRENT_TIME_METHOD_CHOICES = (
        ("latest_from_source", _("Latest From Source")),
        ("previous_to_now", _("Previous to now")),
        ("next_to_now", _("Next to Now")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name=_("title"),
                             help_text=_("The Dataset title as will appear to the public"))
    category = models.ForeignKey(Category, verbose_name=_("category"), on_delete=models.PROTECT)
    sub_category = models.ForeignKey(SubCategory, verbose_name=_("sub_category"), on_delete=models.PROTECT)
    summary = models.CharField(max_length=100, null=True, blank=True,
                               verbose_name=_("summary"),
                               help_text=_("Short summary of less than 100 characters"))
    metadata = models.ForeignKey("Metadata", verbose_name=_("metadata"), null=True, blank=True,
                                 on_delete=models.SET_NULL)
    layer_type = models.CharField(max_length=100, choices=DATASET_TYPE_CHOICES, default="file",
                                  verbose_name=_("layer_type"))
    published = models.BooleanField(default=True, verbose_name=_("published"),
                                    help_text=_("Should the dataset be available for visualization ?"
                                                " If unchecked, the dataset is assumed to be in draft mode "
                                                "and thus not ready"))
    public = models.BooleanField(default=True, verbose_name=_("public"),
                                 help_text=_("Should the dataset be visible to everyone ?"
                                             " If unchecked, only authorized users can view"))
    initial_visible = models.BooleanField(default=False, verbose_name=_("Initially visible on Map by default"),
                                          help_text=_("Make the dataset visible on the map by default"))

    multi_temporal = models.BooleanField(default=True, verbose_name=_("multi-temporal"),
                                         help_text=_("The dataset is multi-temporal"), )

    multi_layer = models.BooleanField(default=False, verbose_name=_("multi-layer"),
                                      help_text=_("The dataset has more than one layer, to be displayed together"), )

    near_realtime = models.BooleanField(default=False, verbose_name=_("near realtime"),
                                        help_text=_(
                                            "Is the layer near realtime?, for example updates every 10 minutes"))

    current_time_method = models.CharField(max_length=100, choices=CURRENT_TIME_METHOD_CHOICES,
                                           default="latest_from_source",
                                           verbose_name=_("current time method"),
                                           help_text=_(
                                               "How to pick default time and for updates, for Multi-Temporal data"))
    auto_update_interval = models.IntegerField(blank=True, null=True, verbose_name=_("Auto Update interval in minutes"),
                                               help_text=_(
                                                   "After how many minutes should the layer auto update on the map to "
                                                   "show current data, if multi-temporal. Leave empty to"
                                                   " disable auto updating"))

    can_clip = models.BooleanField(default=True, verbose_name=_("Enable Clipping by shape"),
                                   help_text=_("Check to enable clipping by boundary or drawn shapes, "
                                               "for raster and vector datasets. Not implemented for WMS types"))

    panels = [
        FieldPanel("title"),
        FieldPanel("category"),
        FieldPanel("sub_category"),
        FieldPanel("layer_type"),
        FieldPanel("summary"),
        FieldPanel("metadata"),
        FieldPanel("published"),
        FieldPanel("public"),
        FieldPanel("initial_visible"),
        FieldPanel("multi_temporal"),
        FieldPanel("multi_layer"),
        FieldPanel("near_realtime"),
        FieldPanel("current_time_method"),
        FieldPanel("auto_update_interval"),
        FieldPanel("can_clip"),
    ]

    def __str__(self):
        return self.title

    @property
    def auto_update_interval_milliseconds(self):
        if self.auto_update_interval:
            return self.auto_update_interval * 60000
        return None

    @property
    def capabilities(self):
        caps = []
        if self.multi_temporal:
            caps.append("timeseries")
        if self.near_realtime:
            caps.append("nearRealTime")
        return caps

    def dataset_url(self):
        admin_helper = AdminURLHelper(self)
        admin_edit_url = admin_helper.get_action_url("index", self.pk)
        return admin_edit_url + f"?id={self.pk}"

    def get_layers_rel(self):
        layer_type = self.layer_type

        if layer_type == "file":
            return self.file_layers

        if layer_type == "vector":
            return self.vector_layers

        if layer_type == "wms":
            return self.wms_layers

        return None

    @property
    def category_url(self):
        if self.category:
            category_admin_helper = AdminURLHelper(Category)
            category_edit_url = category_admin_helper.get_action_url("edit", self.category.pk)
            return category_edit_url
        return None

    @property
    def upload_url(self):
        return get_upload_url(self.layer_type, self.pk)

    def layers_list_url(self):
        list_layer_url = get_layer_action_url(self.layer_type, "index")

        if list_layer_url:
            list_layer_url = list_layer_url + f"?dataset__id__exact={self.pk}"

        return list_layer_url

    def create_layer_url(self):
        if self.has_layers() and not self.multi_layer:
            return None

        create_layer_url = get_layer_action_url(self.layer_type, "create")
        if create_layer_url:
            create_layer_url = create_layer_url + f"?dataset_id={self.pk}"

        return create_layer_url

    @property
    def preview_url(self):
        return get_preview_url(self.layer_type, self.pk)

    def has_layers(self):
        layers = self.get_layers_rel()
        if layers:
            return layers.exists()

        return False

    def can_preview(self):
        return self.has_raster_files() or self.has_vector_tables() or self.has_wms_layers()

    def has_raster_files(self):
        layers = self.file_layers.all()
        has_raster_files = False
        if layers.exists():
            for layer in layers:
                if layer.raster_files.exists():
                    has_raster_files = True
                    break
        return has_raster_files

    def has_vector_tables(self):
        vector_layers = self.vector_layers.all()
        has_vector_tables = False
        if vector_layers.exists():
            for layer in vector_layers:
                if layer.vector_tables.all().exists():
                    has_vector_tables = True
                    break
        return has_vector_tables

    def has_wms_layers(self):
        return self.wms_layers.exists()

    def get_default_layer(self):
        layers = self.get_layers_rel()

        if layers and layers.exists():
            default = layers.filter(default=True)
            if default.exists():
                return default.first().pk
            else:
                return layers.first().pk

        return None

    def get_wms_layers_json(self):
        return []


class Metadata(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name=_("title"), help_text=_("Title of the dataset"))
    subtitle = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("subtitle"),
                                help_text=_("Subtitle if any"))
    function = models.TextField(max_length=255, blank=True, null=True, verbose_name=_("Dataset summary"),
                                help_text=_("Short summary of what the dataset shows. Keep it short."))
    resolution = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("resolution"),
                                  help_text=_("The Spatial resolution of the dataset, for example 10km by 10 km"))
    geographic_coverage = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Geographic coverage"),
                                           help_text=_("The geographic coverage of the dataset. For example East Africa"
                                                       " or specific country name like Ethiopia, or Africa"))
    source = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("source"),
                              help_text=_("The source of the data where was it generated or produced"))
    license = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("license"),
                               help_text=_("Any licensing information for the dataset"))
    frequency_of_update = models.CharField(max_length=255, blank=True, null=True,
                                           verbose_name=_("Frequency of updates"),
                                           help_text=_("How frequent is the dataset updated. "
                                                       "For example daily, weekly, monthly etc"))
    overview = RichTextField(blank=True, null=True, verbose_name=_("detail"),
                             help_text=_("Detail description of the dataset, including the methodology, "
                                         "references or any other relevant information"))
    cautions = RichTextField(blank=True, null=True, verbose_name=_("cautions"),
                             help_text=_("What things should users be aware as they use and interpret this dataset"))
    citation = RichTextField(blank=True, null=True, verbose_name=_("citation"),
                             help_text=_("Scientific citation for this dataset if any. "
                                         "For example the citation for a scientific paper for the dataset"))
    download_data = models.URLField(blank=True, null=True, verbose_name=_("Data download link"),
                                    help_text=_("External link to where the source data can be found and downloaded"))
    learn_more = models.URLField(blank=True, null=True, verbose_name=_("Learn more link"),
                                 help_text=_("External link to where more detail about the dataset can be found"))

    class Meta:
        verbose_name_plural = _("Metadata")

    def __str__(self):
        return self.title


def get_styles():
    from geomanager.models import MBTSource
    return [(style.id, style.name) for style in MBTSource.objects.all()]


class BaseLayer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name=_("title"), help_text=_("layer title"))
    default = models.BooleanField(default=False, verbose_name=_("default"), help_text=_("Is Default Layer"))

    @property
    def edit_url(self):
        edit_url = get_layer_action_url(layer_type=self.dataset.layer_type, action="edit", action_args=self.pk)
        return edit_url

    @property
    def upload_url(self):
        return get_upload_url(layer_type=self.dataset.layer_type, dataset_id=self.dataset.pk, layer_id=self.pk)

    @property
    def preview_url(self):
        return get_preview_url(layer_type=self.dataset.layer_type, dataset_id=self.dataset.pk, layer_id=self.pk)

    class Meta:
        abstract = True


@register_setting
class GeomanagerSettings(BaseSiteSetting):
    GADM_VERSION = (
        ("4.1", "4.1"),
    )

    max_upload_size_mb = models.IntegerField(default=DEFAULT_RASTER_MAX_UPLOAD_SIZE_MB,
                                             verbose_name=_("Maximum upload size in MegaBytes"),
                                             help_text=_(
                                                 "Maximum raster file size that can be uploaded in MegaBytes. "
                                                 "Default is 10Mbs."))

    cap_base_url = models.URLField(max_length=256, null=True, blank=True, verbose_name=_("cap base url"))
    cap_sub_category = models.ForeignKey(SubCategory, null=True, blank=True, verbose_name=_("cap layer sub category"),
                                         on_delete=models.SET_NULL)
    cap_auto_refresh_interval = models.IntegerField(blank=True, null=True,
                                                    verbose_name=_("Auto Refresh interval in minutes"),
                                                    help_text=_(
                                                        "Refresh cap alerts on the map after this minutes. Leave blank "
                                                        "to disable auto refreshing"))
    cap_shown_by_default = models.BooleanField(default=True, verbose_name=_("CAP layer shown by default"),
                                               help_text=_("CAP Layer shown on map by default"))
    cap_metadata = models.ForeignKey(Metadata, on_delete=models.SET_NULL, blank=True, null=True,
                                     verbose_name=_("Metadata"))
    gadm_version = models.CharField(max_length=50, choices=GADM_VERSION, default="4.1",
                                    verbose_name=_("GADM Boundary Data Version"),
                                    help_text=_(
                                        "It is encouraged to use the latest version. "
                                        "See available versions here: https://gadm.org/old_versions.html"))
    tile_gl_fonts_url = models.URLField(max_length=256,
                                        default="https://fonts.openmaptiles.org/{fontstack}/{range}.pbf",
                                        verbose_name=_("GL Styles Font Url"),
                                        help_text=_("GL Styles Font Url"))
    tile_gl_source = models.ForeignKey(MBTSource, blank=True, null=True, on_delete=models.SET_NULL,
                                       verbose_name=_("Open Map Tiles Source"))
    logo = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_("Logo")
    )
    navigation = StreamField([
        ('menu_items', blocks.ListBlock(NavigationItemsBlock(max_num=8))),
    ], block_counts={
        'menu_items': {'max_num': 1},
    }, use_json_field=True, null=True, blank=True)

    base_maps = StreamField([
        ('basemap', blocks.StructBlock([
            ('label', blocks.CharBlock(label=_("label"))),
            ('backgroundColor', blocks.CharBlock(label=_("background color"))),
            ('image', ImageChooserBlock(required=False, label=_("image"))),
            ('basemapGroup', blocks.CharBlock(label=_("basemap group"))),
            ('labelsGroup', blocks.CharBlock(label=_("labels group"))),
            ('url', blocks.URLBlock(required=False, label=_("url"))),
            ('default', blocks.BooleanBlock(required=False, label=_("default"), help_text=_("Is default style ?"))),
        ]))
    ], use_json_field=True, null=True, blank=True)

    edit_handler = TabbedInterface([
        ObjectList([
            FieldPanel("max_upload_size_mb"),
        ], heading=_("Upload Settings")),
        ObjectList([
            FieldPanel("tile_gl_fonts_url"),
            FieldPanel("tile_gl_source"),
            FieldPanel("base_maps"),
        ], heading=_("Basemap TileServer Settings")),
        ObjectList([
            FieldPanel("cap_base_url"),
            FieldPanel("cap_sub_category"),
            FieldPanel("cap_auto_refresh_interval"),
            FieldPanel("cap_shown_by_default"),
            FieldPanel("cap_metadata"),
        ], heading=_("CAP Layer Settings")),
        ObjectList([
            FieldPanel("logo"),
            FieldPanel("navigation"),
        ], heading=_("Branding Settings")),
    ])

    @property
    def cap_auto_refresh_interval_milliseconds(self):
        if self.cap_auto_refresh_interval:
            return self.cap_auto_refresh_interval * 60000
        return None

    @property
    def max_upload_size_bytes(self):
        return self.max_upload_size_mb * 1024 * 1024
