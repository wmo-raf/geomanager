from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from wagtail.admin.panels import FieldPanel, MultiFieldPanel

from geomanager.models.core import BaseLayer, Dataset
from geomanager.utils import DATE_FORMAT_CHOICES

DEFAULT_OPENMETEO_BASE_URL = "https://openmeteo.s3.amazonaws.com/data_spatial"


class OpenMeteoLayer(TimeStampedModel, BaseLayer):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="openmeteo_layers",
                                verbose_name=_("dataset"))

    base_url = models.CharField(
        max_length=2048,
        default=DEFAULT_OPENMETEO_BASE_URL,
        verbose_name=_("Data base URL"),
        help_text=_("Root URL of the Open-Meteo spatial data, holding one folder per weather model"),
    )
    domain = models.CharField(
        max_length=100,
        verbose_name=_("Weather model"),
        help_text=_("Open-Meteo domain of the weather model, e.g. dwd_icon, ecmwf_ifs025, ncep_gfs025. "
                    "Its latest run is read from <base URL>/<domain>/latest.json"),
    )
    variable = models.CharField(
        max_length=100,
        verbose_name=_("Variable"),
        help_text=_("Weather variable to display, e.g. temperature_2m, precipitation, wind_speed_10m. "
                    "The variables of a model are listed in its latest.json"),
    )

    date_format = models.CharField(max_length=100, choices=DATE_FORMAT_CHOICES, blank=True, null=True,
                                   default="yyyy-MM-dd HH:mm",
                                   verbose_name=_("Display Format for DateTime Selector"))

    class Meta:
        verbose_name = _("Open-Meteo Layer")
        verbose_name_plural = _("Open-Meteo Layers")
        ordering = ['order']

    panels = [
        FieldPanel("dataset"),
        FieldPanel("title"),
        FieldPanel("default"),
        MultiFieldPanel([
            FieldPanel("base_url"),
            FieldPanel("domain"),
            FieldPanel("variable"),
        ], heading=_("Open-Meteo source")),
        FieldPanel("date_format"),
    ]

    def __str__(self):
        return f"{self.dataset.title} - {self.title}"

    @property
    def openmeteo_config(self):
        return {
            "baseUrl": self.base_url.rstrip("/"),
            "domain": self.domain,
            "variable": self.variable,
        }

    def layer_config(self, request=None):
        # the source of the selected time is built by the map viewer from the
        # model run listed in latest.json
        return {
            "type": "raster",
            "source": {
                "type": "openmeteo",
                "url": f"{self.base_url.rstrip('/')}/{self.domain}/latest.json",
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
        # built by the map viewer from the color scale the Open-Meteo protocol
        # renders the variable with
        return {"type": "openmeteo", "items": []}

    def clean(self):
        if self._state.adding:
            if self.dataset.has_layers() and not self.dataset.multi_layer:
                raise ValidationError(_("Can not add layer because the dataset is not marked as Multi Layer. "
                                        "To add multiple layers to a dataset, please mark the dataset as "
                                        "Multi Layer and try again"))

        if self.domain and "/" in self.domain:
            raise ValidationError({"domain": _("The weather model must be a single folder name, without '/'")})
