from urllib.parse import parse_qs, urlencode, urlparse

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel, InlinePanel
from wagtail.api.v2.utils import get_full_url
from wagtail.fields import StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.images.models import Image
from wagtail.models import Orderable

from geomanager.blocks import (
    InlineLegendBlock,
    LayerMoreInfoBlock,
    QueryParamSelectableBlock
)
from geomanager.models.core import Dataset, BaseLayer
from geomanager.utils import DATE_FORMAT_CHOICES


class WmsLayer(TimeStampedModel, ClusterableModel, BaseLayer):
    OUTPUT_FORMATS = (
        ("image/png", "PNG"),
        ("image/jpeg", "JPEG"),
        ("image/gif", "GIF"),
    )

    VERSION_CHOICES = (
        ("1.1.1", "1.1.1"),
        ("1.3.0", "1.3.0"),
    )

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="wms_layers", verbose_name=_("dataset"))
    request_time_from_capabilities = models.BooleanField(default=True, verbose_name=_("Request time from capabilities"),
                                                         help_text=_("Get list of available times for this layer"
                                                                     " from getCapabilities"), )
    base_url = models.CharField(max_length=500, verbose_name=_("base url for WMS"), )
    version = models.CharField(max_length=50, default="1.1.1", choices=VERSION_CHOICES, verbose_name=_("WMS Version"))
    width = models.IntegerField(default=256, verbose_name=_("Pixel Width"),
                                help_text=_("The size of the map image in pixels along the i axis"), )
    height = models.IntegerField(default=256, verbose_name=_("Pixel Height"),
                                 help_text=_("The size of the map image in pixels along the j axis"), )
    transparent = models.BooleanField(default=True, verbose_name=_("Transparency"),
                                      help_text=_("Ability of underlying maps to be visible or not"), )
    srs = models.CharField(max_length=50, default="EPSG:3857", verbose_name=_("Spatial Reference System"),
                           help_text=_("WMS Spatial Reference e.g EPSG:3857"), )
    format = models.CharField(max_length=50, default="image/png", choices=OUTPUT_FORMATS,
                              verbose_name=_("Output Format"),
                              help_text=_(
                                  "Allowed map formats are either “picture” formats or “graphic element” formats."), )
    wms_query_params_selectable = StreamField([
        ('param', QueryParamSelectableBlock(label=_("Query Parameter")))
    ], use_json_field=True, null=True, blank=True, verbose_name=_("WMS Query Params With selectable Options"),
        help_text=_(
            "This should provide a list of options that users can choose to change the query parameter of the url"))

    params_selectors_side_by_side = models.BooleanField(default=False,
                                                        verbose_name=_("Arrange Param Selectors side by side"))
    legend = StreamField([
        ('legend', InlineLegendBlock(label=_("Custom Legend")),),
        ('legend_image', ImageChooserBlock(label=_("Custom Image")),),
    ], use_json_field=True, null=True, blank=True, max_num=1, verbose_name=_("Legend"), )
    legend_from_capabilities = models.BooleanField(
        default=False,
        verbose_name=_("Load legend from WMS capabilities"),
        help_text=_("If checked, the legend will be loaded from the WMS GetCapabilities response "
                     "(LegendURL). This takes precedence over custom legend options above."),
    )

    date_format = models.CharField(max_length=100, choices=DATE_FORMAT_CHOICES, blank=True, null=True,
                                   verbose_name=_("Display Format for DateTime Selector"))
    custom_get_capabilities_url = models.URLField(blank=True, null=True, verbose_name=_("Get Capabilities URL"),
                                                  help_text=_("Alternative URL for the GetCapabilities request. "
                                                              "Used when 'Request time from capabilities' "
                                                              "option is checked. Leave blank to use base url."))
    get_capabilities_layer_name = models.CharField(max_length=255, blank=True, null=True,
                                                   verbose_name=_("Get Capabilities Layer Name"),
                                                   help_text=_("Alternative layer name for the GetCapabilities request"
                                                               ))
    more_info = StreamField([
        ('more_info', LayerMoreInfoBlock(label=_("Info link")),),
    ], block_counts={
        'more_info': {'max_num': 1},
    }, use_json_field=True, null=True, blank=True, max_num=1, verbose_name=_("More Info"), )

    class Meta:
        verbose_name = _("WMS Layer")
        verbose_name_plural = _("WMS Layers")
        ordering = ['order']

    panels = [
        FieldPanel("dataset"),
        FieldPanel("title"),
        FieldPanel("default"),
        FieldPanel("date_format"),
        MultiFieldPanel([
            FieldPanel("base_url"),
            FieldPanel("version"),
            FieldRowPanel([
                FieldPanel("width", classname="col6"),
                FieldPanel("height", classname="col6"),
            ]),
            FieldPanel("transparent"),
            FieldPanel("srs"),
            FieldPanel("format"),
            InlinePanel("wms_request_layers", heading=_("WMS Request Layers"),
                        label=_("WMS Request Layer"), min_num=1),
            InlinePanel("wms_request_styles", heading=_("WMS Request Styles"),
                        label=_("WMS Request Style")),
            InlinePanel("wms_request_params", heading=_("WMS Request Additional Parameters"),
                        label=_("WMS Request Param")),
            FieldPanel("wms_query_params_selectable"),
        ], heading=_("WMS GetMap Configuration")),
        MultiFieldPanel([
            FieldPanel("request_time_from_capabilities"),
            FieldPanel("custom_get_capabilities_url"),
            FieldPanel("get_capabilities_layer_name"),
        ], heading=_("WMS GetCapabilities Configuration")),
        FieldPanel("params_selectors_side_by_side"),
        MultiFieldPanel([
            FieldPanel("legend"),
            FieldPanel("legend_from_capabilities"),
        ], heading=_("Legend")),
        FieldPanel("more_info"),
    ]

    def __str__(self):
        return self.title

    def get_selectable_params(self):
        params = {}
        if self.wms_query_params_selectable:
            for query_param in self.wms_query_params_selectable:
                data = query_param.block.get_api_representation(query_param.value)
                val = f"{data.get('name')}"
                params.update({val: data})
        return params

    def get_wms_params(self):
        params = {
            "SERVICE": "WMS",
            "VERSION": self.version,
            "REQUEST": "GetMap",
            "TRANSPARENT": self.transparent,
            "LAYERS": ",".join([layer.name for layer in self.wms_request_layers.all()]),
            "STYLES": ",".join([style.name for style in self.wms_request_styles.all()]),
            "BBOX": "{bbox-epsg-3857}",
            "WIDTH": self.width,
            "HEIGHT": self.height,
            "FORMAT": self.format,
        }

        if self.version == "1.3.0":
            params.update({"CRS": self.srs})
        else:
            params.update({"SRS": self.srs})

        extra_params = {param.name: param.value for param in self.wms_request_params.all()}
        params.update(**extra_params)

        return params

    @staticmethod
    def _merge_query_params(url, params):
        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        query.update({k: [v] for k, v in params.items()})
        return parsed._replace(query=urlencode(query, doseq=True)).geturl()

    @property
    def get_map_url(self):
        params = self.get_wms_params()
        selectable_params = self.get_selectable_params()

        for key, val in selectable_params.items():
            key_val = key
            if key.upper() in params:
                key_val = key.upper()
            params.update({key_val: f"{{{key}}}"})

        return self._merge_query_params(self.base_url, params)

    def get_selectable_params_config(self):
        selectable_params = self.get_selectable_params()
        config = []

        for key, param_config in selectable_params.items():
            param_config = {
                "key": key,
                "required": True,
                "type": param_config.get("type"),
                "options": param_config.get("options"),
                "sentence": f"{param_config.get('label') or key} {{selector}}",
            }

            config.append(param_config)

        return config

    @property
    def get_capabilities_url(self):
        if self.request_time_from_capabilities:
            capabilities_url = self.base_url

            if self.custom_get_capabilities_url:
                capabilities_url = self.custom_get_capabilities_url

            params = {
                "SERVICE": "WMS",
                "VERSION": self.version,
                "REQUEST": "GetCapabilities",
            }

            return self._merge_query_params(capabilities_url, params)
        return None

    @property
    def layer_config(self):
        wms_url = self.get_map_url
        if self.dataset.multi_temporal:
            wms_url = f"{wms_url}&time={{time}}"

        layer_config = {
            "type": "raster",
            "source": {
                "type": "raster",
                "tiles": [wms_url]
            }
        }

        return layer_config

    @property
    def params(self):
        params = {}
        if self.dataset.multi_temporal:
            params.update({"time": ""})

        selector_config = self.get_selectable_params_config()

        for selector_param in selector_config:
            default = None
            for option in selector_param.get("options"):
                if option.get("default"):
                    default = option.get("value")
                    break
            if not default:
                default = selector_param.get("options")[0].get("value")
            params.update({selector_param.get("key"): default})

        return params

    @property
    def time_parameter_selector_config(self):
        time_config = None
        if self.dataset.multi_temporal:
            time_config = {
                "key": "time",
                "required": True,
                "sentence": "{selector}",
                "type": "datetime",
                "availableDates": [],
            }

            if self.date_format:
                if self.date_format == "pentadal":
                    time_config.update({
                        "dateFormat": {"currentTime": "MMM yyyy", "asPeriod": "pentadal"},
                    })
                elif self.date_format == "dekadal":
                    time_config.update({
                        "dateFormat": {"currentTime": "MMM yyyy", "asPeriod": "dekadal"},
                    })
                else:
                    time_config.update({
                        "dateFormat": {"currentTime": self.date_format},
                    })
            else:
                time_config.update({
                    "dateFormat": {"currentTime": "yyyy-MM-dd HH:mm"},
                })

        return time_config

    @property
    def param_selector_config(self):
        config = []

        time_config = self.time_parameter_selector_config
        if time_config:
            config.append(time_config)

        selectable_params_config = self.get_selectable_params_config()
        config.extend(selectable_params_config)

        return config

    def get_legend_config(self, request):

        # default config
        config = {
            "type": "basic",
            "items": []
        }

        # legend from WMS capabilities takes precedence
        if self.legend_from_capabilities:
            config.update({"type": "wms_capabilities"})
            return config

        legend_block = self.legend

        # only one legend block entry is expected
        if legend_block:
            legend_block = legend_block[0]

        if legend_block:
            if isinstance(legend_block.value, Image):
                image_url = legend_block.value.file.url
                if request:
                    image_url = get_full_url(request, image_url)
                config.update({"type": "image", "imageUrl": image_url})
                return config

            data = legend_block.block.get_api_representation(legend_block.value)

            config.update({"type": data.get("type")})

            for item in data.get("items"):
                config["items"].append({
                    "name": item.get("value"),
                    "color": item.get("color")
                })

        return config

    @property
    def layer_name(self):
        return self.wms_request_layers.all()[0].name

    def get_analysis_config(self):
        analysis_config = []

        return analysis_config

    def get_more_info(self):
        more_info = self.more_info

        return {}


class WmsRequestLayer(Orderable):
    layer = ParentalKey(WmsLayer, on_delete=models.CASCADE, related_name="wms_request_layers",
                        verbose_name=_("WMS Request Layers"))
    name = models.CharField(max_length=250, null=False, blank=False,
                            verbose_name=_("name"),
                            help_text=_("WMS Layer is requested by using this "
                                        "name in the LAYERS parameter of a "
                                        "GetMap request."))

    class Meta:
        verbose_name = _("WMS Request Layer")
        verbose_name_plural = _("WMS Request Layers")


class WmsRequestStyle(Orderable):
    layer = ParentalKey(WmsLayer, on_delete=models.CASCADE,
                        related_name="wms_request_styles", verbose_name=_("WMS Request Styles"))
    name = models.CharField(max_length=250, null=False, blank=False,
                            verbose_name=_("name"),
                            help_text=_("The style's Name is used in the Map request STYLES parameter"))

    class Meta:
        verbose_name = _("WMS Request Style")
        verbose_name_plural = _("WMS Request Styles")


class WmsRequestParam(Orderable):
    layer = ParentalKey(WmsLayer, on_delete=models.CASCADE, related_name="wms_request_params",
                        verbose_name=_("WMS Requests Additional Parameters", ))
    name = models.CharField(max_length=250, null=False, blank=False, verbose_name=_("name"),
                            help_text=_("Name of the parameter"))
    value = models.CharField(max_length=250, null=False, blank=False, help_text=_("Value of the parameter"))

    class Meta:
        verbose_name = _("WMS Request Parameter")
        verbose_name_plural = _("WMS Request Parameters")
