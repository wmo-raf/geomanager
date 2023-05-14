import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, TabbedInterface, ObjectList, InlinePanel
from wagtail.contrib.modeladmin.helpers import AdminURLHelper
from wagtail.contrib.settings.models import BaseSiteSetting
from wagtail.contrib.settings.registry import register_setting
from wagtail.fields import StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Orderable
from wagtail_adminsortable.models import AdminSortable
from wagtailhumanitarianicons.widgets import IconChooserWidget

from layermanager.helpers import get_layer_action_url, get_preview_url, get_upload_url
from layermanager.utils.vector_utils import ensure_pg_service_schema_exists

DEFAULT_RASTER_MAX_UPLOAD_SIZE_MB = 10


class Category(TimeStampedModel, AdminSortable, ClusterableModel):
    title = models.CharField(max_length=255, verbose_name=_("title"), help_text=_("Title of the category"))
    icon = models.CharField(max_length=255, verbose_name=_("icon"), blank=True, null=True)
    active = models.BooleanField(default=True, verbose_name=_("active"), help_text=_("Is the category active ?"))
    public = models.BooleanField(default=False, verbose_name=_("public"), help_text=_("Is the category public ?"))

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
        ("vector", "Vector"),
        ("wms", "WMS"),
    )

    CURRENT_TIME_METHOD_CHOICES = (
        ("latest_from_source", _("Latest From Source")),
        ("previous_to_now", _("Previous to now")),
        ("next_to_now", _("Next to Now")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name=_("title"),
                             help_text=_("The Dataset title as will appear to the public"))
    category = models.ForeignKey(Category, verbose_name=_("category"), null=True, blank=True, on_delete=models.SET_NULL)
    sub_category = models.ForeignKey(SubCategory, verbose_name=_("sub_category"), null=True, blank=True,
                                     on_delete=models.SET_NULL)
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

    panels = [
        FieldPanel("category"),
        FieldPanel("sub_category"),
        FieldPanel("layer_type"),
        FieldPanel("title"),
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
    title = models.CharField(max_length=255, verbose_name=_("title"))

    class Meta:
        verbose_name_plural = _("Metadata")

    panels = [
        FieldPanel("title")
    ]

    def __str__(self):
        return {self.title}


def get_styles():
    from layermanager.models.tile_gl import TileGlStyle
    return [(style.id, style.name) for style in TileGlStyle.objects.all()]


@register_setting
class LayerManagerSettings(BaseSiteSetting):
    max_upload_size_mb = models.IntegerField(default=DEFAULT_RASTER_MAX_UPLOAD_SIZE_MB,
                                             verbose_name=_("Maximum upload size in MegaBytes"),
                                             help_text=_(
                                                 "Maximum raster file size that can be uploaded in MegaBytes. "
                                                 "Default is 10Mbs."))

    pg_service_schema = models.CharField(max_length=100, default="vectordata",
                                         verbose_name=_("vector database schema"),
                                         help_text=_("Postgis vector database schema"))
    pg_service_user = models.CharField(max_length=100, default="vectordata_user",
                                       verbose_name=_("vector database user"), help_text=_("Postgis vector data user"))
    pg_service_user_password = models.CharField(max_length=100,
                                                verbose_name=_("vector database user password"),
                                                help_text=_("Postgis vector data user password"))
    tile_gl_fonts_url = models.URLField(max_length=256,
                                        default="https://fonts.openmaptiles.org/{fontstack}/{range}.pbf",
                                        verbose_name=_("GL Styles Font Url"),
                                        help_text=_("GL Styles Font Url"))
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

    base_maps = StreamField([
        ('basemap', blocks.StructBlock([
            ('label', blocks.CharBlock(label=_("label"))),
            ('backgroundColor', blocks.CharBlock(label=_("background color"))),
            ('image', ImageChooserBlock(required=False, label=_("image"))),
            ('basemapGroup', blocks.CharBlock(label=_("basemap group"))),
            ('labelsGroup', blocks.CharBlock(label=_("labels group"))),
            ('mapStyle', blocks.ChoiceBlock(choices=get_styles, lable=_("map style"))),
            ('url', blocks.URLBlock(required=False, label=_("url"))),
            ('default', blocks.BooleanBlock(required=False, label=_("default"), help_text=_("Is default style ?"))),
        ]))
    ], use_json_field=True, null=True, blank=True)

    edit_handler = TabbedInterface([
        ObjectList([
            FieldPanel("max_upload_size_mb"),
        ], heading=_("Upload Settings")),
        ObjectList([
            FieldPanel("pg_service_schema"),
            FieldPanel("pg_service_user"),
            FieldPanel("pg_service_user_password"),
        ], heading=_("Vector DB Settings")),
        ObjectList([
            FieldPanel("tile_gl_fonts_url"),
            FieldPanel("base_maps"),
        ], heading=_("Basemap TileServer Settings")),
        ObjectList([
            FieldPanel("cap_base_url"),
            FieldPanel("cap_sub_category"),
            FieldPanel("cap_auto_refresh_interval"),
            FieldPanel("cap_shown_by_default"),
        ], heading=_("CAP Layer Settings")),
    ])

    @property
    def cap_auto_refresh_interval_milliseconds(self):
        if self.cap_auto_refresh_interval:
            return self.cap_auto_refresh_interval * 60000
        return None

    @property
    def max_upload_size_bytes(self):
        return self.max_upload_size_mb * 1024 * 1024

    def save(self, *args, **kwargs):
        if self.pg_service_schema and self.pg_service_user and self.pg_service_user_password:
            ensure_pg_service_schema_exists(self.pg_service_schema, self.pg_service_user, self.pg_service_user_password)
        super(LayerManagerSettings, self).save(*args, **kwargs)


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
