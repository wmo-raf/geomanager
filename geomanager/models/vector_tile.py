from django.contrib.admin.utils import quote
from django.core.files.base import ContentFile
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_json_widget.widgets import JSONEditorWidget
from modelcluster.fields import ParentalKey
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import StreamField

from geomanager.blocks import (
    FillVectorLayerBlock,
    LineVectorLayerBlock,
    CircleVectorLayerBlock,
    IconVectorLayerBlock,
    TextVectorLayerBlock,
)
from geomanager.models.core import Dataset
from geomanager.models.tile_base import BaseTileLayer
from geomanager.utils import DATE_FORMAT_CHOICES
from geomanager.utils.svg import rasterize_svg_to_png
from geomanager.utils.tiles import get_vector_render_layers


class TileFillVectorLayerBlock(FillVectorLayerBlock):
    source_layer = blocks.CharBlock(required=True, label=_("source layer"))


class TileLineVectorLayerBlock(LineVectorLayerBlock):
    source_layer = blocks.CharBlock(required=True, label=_("source layer"))


class TileCircleVectorLayerBlock(CircleVectorLayerBlock):
    source_layer = blocks.CharBlock(required=True, label=_("source layer"))


class TileIconVectorLayerBlock(IconVectorLayerBlock):
    source_layer = blocks.CharBlock(required=True, label=_("source layer"))


class TileTextVectorLayerBlock(TextVectorLayerBlock):
    source_layer = blocks.CharBlock(required=True, label=_("source layer"))


class PopupFieldBlock(blocks.StructBlock):
    DATA_TYPE_CHOICES = (
        ("string", _("String")),
        ("number", _("Number")),
    )

    data_key = blocks.CharBlock(required=True, label=_("Data Key"))
    label = blocks.CharBlock(required=True, label=_("Popup Label"))
    data_type = blocks.ChoiceBlock(choices=DATA_TYPE_CHOICES, default="string", label=_("Data Type"))


class VectorTileLayer(BaseTileLayer):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="vector_tile_layers",
                                verbose_name=_("dataset"))

    is_pmtiles = models.BooleanField(default=False, verbose_name=_("PMTiles format"),
                                     help_text=_("Check if the URL points to a PMTiles file instead of XYZ tiles"))

    render_layers = StreamField([
        ("fill", TileFillVectorLayerBlock(label=_("Polygon Layer"))),
        ("line", TileLineVectorLayerBlock(label=_("Line Layer"))),
        ("circle", TileCircleVectorLayerBlock(label=_("Point Layer"))),
        ("icon", TileIconVectorLayerBlock(label=_("Icon Layer"))),
        ("text", TileTextVectorLayerBlock(label=_("Text Label Layer"))),
    ], use_json_field=True, null=True, blank=True, verbose_name=_("Render Layers"))

    use_render_layers_json = models.BooleanField(default=False, verbose_name=_("Use Render Layers JSON"))
    render_layers_json = models.JSONField(blank=True, null=True, verbose_name=_("Layers Configuration"))

    popup_config = StreamField([
        ("popup_fields", PopupFieldBlock(label=_("Popup Fields"))),
    ], use_json_field=True, null=True, blank=True, verbose_name=_("Map Popup Configuration"))

    class Meta:
        verbose_name = _("Vector Tile Layer")
        verbose_name_plural = _("Vector Tile Layers")
        ordering = ['order']

    panels = [
        FieldPanel("dataset"),
        FieldPanel("title"),
        FieldPanel("default"),
        FieldPanel("is_pmtiles"),
        FieldPanel("base_url"),

        MultiFieldPanel([
            FieldPanel("get_time_from_tile_json"),
            FieldPanel("tile_json_url", classname="show_if_get_time_checked"),
            FieldPanel("timestamps_response_object_key", classname="show_if_get_time_checked"),
            FieldPanel("time_parameter_name", classname="show_if_get_time_checked"),
            FieldPanel("date_format", classname="show_if_get_time_checked"),
        ], heading=_("Time Settings")),

        FieldPanel("query_params_static"),
        FieldPanel("query_params_selectable"),
        FieldPanel("params_selectors_side_by_side"),
        FieldPanel("legend"),
        FieldPanel("more_info"),
        FieldPanel("use_render_layers_json"),
        FieldPanel("render_layers"),
        FieldPanel('render_layers_json', widget=JSONEditorWidget(width="100%")),
        FieldPanel('popup_config'),
    ]

    def __str__(self):
        return self.title

    @property
    def preview_url(self):
        preview_url = reverse(
            f"geomanager_preview_vector_tile_layer",
            args=[quote(self.dataset.pk), quote(self.pk)],
        )
        return preview_url

    @property
    def layer_config(self):
        tile_url = self.tile_url

        if self.is_pmtiles:
            layer_config = {
                "type": "vector",
                "source": {
                    "type": "vector",
                    "url": f"pmtiles://{self.base_url}",
                }
            }
        else:
            layer_config = {
                "type": "vector",
                "source": {
                    "type": "vector",
                    "tiles": [tile_url]
                }
            }

        if self.use_render_layers_json and self.render_layers_json:
            layer_config.update({"render": {"layers": self.render_layers_json}})
            return layer_config

        render_layers = get_vector_render_layers(self.render_layers)

        layer_config.update({"render": {"layers": render_layers}})

        return layer_config

    @property
    def interaction_config(self):
        if not self.popup_config:
            return None

        config = {
            "type": "intersection",
            "output": []
        }

        for popup_field in self.popup_config:
            config["output"].append({
                "column": popup_field.value.get("data_key"),
                "property": popup_field.value.get("label"),
                "type": popup_field.value.get("data_type", "string"),
            })

        return config

    def save(self, *args, **kwargs):
        # remove existing icons for this layer.
        # TODO: Find efficient way to update exising icons, while deleting obsolete ones
        VectorTileLayerIcon.objects.filter(layer=self).delete()

        for render_layer in self.render_layers:
            if render_layer.block_type == "icon":
                icon_image = render_layer.value.get("layout").get("icon_image")
                icon_color = render_layer.value.get("paint").get("icon_color")
                png_bytes = rasterize_svg_to_png(icon_image, fill_color=icon_color)

                if png_bytes:
                    layer_icon = VectorTileLayerIcon(name=icon_image, color=icon_color)
                    layer_icon.file = ContentFile(png_bytes.getvalue(), f"{icon_image}.{icon_color}.png")
                    self.icons.add(layer_icon)

        super().save(*args, **kwargs)


class VectorTileLayerIcon(models.Model):
    layer = ParentalKey(VectorTileLayer, on_delete=models.CASCADE, related_name="icons")
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=100, null=True)
    file = models.FileField(upload_to="vector_tile_icons/")

    def __str__(self):
        return f"{self.layer.title}-{self.name}-{self.color}"
