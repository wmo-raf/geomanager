from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from dateutil.relativedelta import relativedelta
from django_extensions.db.models import TimeStampedModel
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.api.v2.utils import get_full_url
from wagtail.fields import StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.images.models import Image
from wagtail_modeladmin.helpers import AdminURLHelper

from geomanager.blocks import InlineLegendBlock
from geomanager.models.core import BaseLayer, Dataset
from geomanager.models.raster_style import RasterStyle
from geomanager.utils import DATE_FORMAT_CHOICES


TIME_STEP_UNIT_CHOICES = (
    ("years", _("Years")),
    ("months", _("Months")),
    ("days", _("Days")),
    ("hours", _("Hours")),
)

TIME_PLACEHOLDER_KEYS = ("time", "year", "month", "day", "hour")


class RasterCOGLayer(TimeStampedModel, BaseLayer):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="raster_cog_layers",
                                verbose_name=_("dataset"))

    url_template = models.CharField(
        max_length=2048,
        verbose_name=_("COG URL template"),
        help_text=_("URL template with a time placeholder. Supported placeholders: "
                    "{time:strftime} (e.g. {time:%Y}, {time:%Y-%m-%d}), {year}, {month}, {day}, {hour}. "
                    "Example: https://example.org/data/file_{time:%Y}.tif"),
    )
    time_start = models.DateTimeField(
        verbose_name=_("Start time"),
        help_text=_("First timestamp of the series (inclusive)"),
    )
    time_end = models.DateTimeField(
        verbose_name=_("End time"),
        help_text=_("Last timestamp of the series (inclusive)"),
    )
    time_step_value = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Time step value"),
    )
    time_step_unit = models.CharField(
        max_length=20,
        choices=TIME_STEP_UNIT_CHOICES,
        default="years",
        verbose_name=_("Time step unit"),
    )

    date_format = models.CharField(max_length=100, choices=DATE_FORMAT_CHOICES, blank=True, null=True,
                                   default="yyyy-MM-dd HH:mm",
                                   verbose_name=_("Display Format for DateTime Selector"))
    style = models.ForeignKey("RasterStyle", null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("style"))
    use_custom_legend = models.BooleanField(default=False, verbose_name=_("Use custom legend"))
    legend = StreamField([
        ('legend', InlineLegendBlock(label=_("Custom Legend")),),
        ('legend_image', ImageChooserBlock(label=_("Custom Image")),),
    ], use_json_field=True, null=True, blank=True, max_num=1, verbose_name=_("Legend"), )

    class Meta:
        verbose_name = _("Raster COG Layer")
        verbose_name_plural = _("Raster COG Layers")
        ordering = ['order']

    panels = [
        FieldPanel("dataset"),
        FieldPanel("title"),
        FieldPanel("default"),
        MultiFieldPanel([
            FieldPanel("url_template"),
            FieldPanel("time_start"),
            FieldPanel("time_end"),
            FieldPanel("time_step_value"),
            FieldPanel("time_step_unit"),
        ], heading=_("COG source")),
        FieldPanel("date_format"),
        FieldPanel("style"),
        FieldPanel("use_custom_legend"),
        FieldPanel("legend"),
    ]

    def __str__(self):
        return f"{self.dataset.title} - {self.title}"

    def get_style_url(self):
        url = {"action": _("Create Style")}
        style_admin_helper = AdminURLHelper(RasterStyle)
        if self.style:
            url.update({
                "action": _("Edit Style"),
                "url": style_admin_helper.get_action_url("edit", self.style.pk)
            })
        else:
            url.update({
                "url": style_admin_helper.get_action_url("create") + f"?layer_id={str(self.pk)}"
            })
        return url

    def _format_url(self, tick):
        return self.url_template.format(
            time=tick,
            year=tick.year,
            month=tick.month,
            day=tick.day,
            hour=tick.hour,
        )

    def enumerate_entries(self):
        delta = relativedelta(**{self.time_step_unit: self.time_step_value})
        entries = []
        current = self.time_start
        # Guard against zero-step infinite loop (validated in clean(), but cheap belt-and-braces)
        if self.time_step_value == 0:
            return [(self.time_start, self._format_url(self.time_start))]

        while current <= self.time_end:
            entries.append((current, self._format_url(current)))
            current = current + delta
        return entries

    def get_color_ramp(self):
        if self.style:
            return self.style.get_color_ramp()
        return None

    def get_tile_json_url(self, request=None):
        url = reverse("raster_cog_tilejson", args=(self.id,))
        if request:
            url = get_full_url(request, url)
        return url

    def layer_config(self, request=None):
        return {
            "type": "raster",
            "source": {
                "type": "cog",
                "tilejson": self.get_tile_json_url(request),
            }
        }

    @property
    def params(self):
        return {"time": ""}

    @property
    def param_selector_config(self):
        if self.dataset.multi_layer:
            default_layer = self.dataset.layers.filter(default=True).exclude(pk=self.pk).first()
            if default_layer:
                return default_layer.param_selector_config

        time_config = {
            "key": "time",
            "required": True,
            "sentence": "{selector}",
            "type": "datetime",
            "availableDates": [],
        }

        if self.date_format:
            if self.date_format == "pentadal":
                time_config.update({"dateFormat": {"currentTime": "MMM yyyy", "asPeriod": "pentadal"}})
            elif self.date_format == "dekadal":
                time_config.update({"dateFormat": {"currentTime": "MMM yyyy", "asPeriod": "dekadal"}})
            else:
                time_config.update({"dateFormat": {"currentTime": self.date_format}})
        else:
            time_config.update({"dateFormat": {"currentTime": "yyyy-MM-dd HH:mm"}})

        return [time_config]

    def get_legend_config(self, request=None):
        config = {"type": "choropleth", "items": []}

        if self.style:
            if self.use_custom_legend:
                legend_block = self.legend
                if legend_block:
                    legend_block = legend_block[0]

                if legend_block:
                    if isinstance(legend_block.value, Image):
                        image_url = legend_block.value.file.url
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

            return self.style.get_legend_config()

        return config

    def get_tile_json(self, request=None):
        entries = self.enumerate_entries()
        timestamps = [t.strftime("%Y-%m-%dT%H:%M:%S.000Z") for t, _u in entries]
        urls = {t.strftime("%Y-%m-%dT%H:%M:%S.000Z"): u for t, u in entries}

        return {
            "tilejson": "3.0.0",
            "name": self.title,
            "scheme": "xyz",
            "time_parameter": "time",
            "timestamps": timestamps,
            "urls": urls,
        }

    def clean(self):
        if self._state.adding:
            if self.dataset.has_layers() and not self.dataset.multi_layer:
                raise ValidationError(_("Can not add layer because the dataset is not marked as Multi Layer. "
                                        "To add multiple layers to a dataset, please mark the dataset as "
                                        "Multi Layer and try again"))

        if self.time_end and self.time_start and self.time_end < self.time_start:
            raise ValidationError({"time_end": _("End time must be greater than or equal to start time")})

        if self.time_step_value == 0:
            raise ValidationError({"time_step_value": _("Time step value must be greater than 0")})

        if self.url_template:
            has_placeholder = any(f"{{{key}" in self.url_template for key in TIME_PLACEHOLDER_KEYS)
            if not has_placeholder:
                raise ValidationError({"url_template": _(
                    "URL template must contain at least one time placeholder "
                    "({time:strftime}, {year}, {month}, {day} or {hour})"
                )})

            if self.time_start:
                try:
                    start_url = self._format_url(self.time_start)
                except (KeyError, IndexError, ValueError) as e:
                    raise ValidationError({"url_template": _("Invalid URL template: %(error)s") % {"error": str(e)}})

                if self.time_end and self.time_end != self.time_start:
                    end_url = self._format_url(self.time_end)
                    if start_url == end_url:
                        raise ValidationError({"url_template": _(
                            "URL template produces the same URL for start and end times. "
                            "Add a time-dependent placeholder."
                        )})
