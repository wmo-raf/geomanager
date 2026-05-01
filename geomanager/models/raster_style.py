from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel, InlinePanel
from wagtail.models import Orderable
from wagtail_color_panel.edit_handlers import NativeColorPanel
from wagtail_color_panel.fields import ColorField

from geomanager.forms import RasterStyleModelForm
from geomanager.utils import significant_digits, round_to_precision
from geomanager.widgets import RasterStyleWidget


class RasterStyle(TimeStampedModel, ClusterableModel):
    LEGEND_TYPE_CHOICES = (
        ("basic", _("Basic")),
        ("choropleth", _("Choropleth Horizontal")),
        ("choropleth_vertical", _("Choropleth Vertical")),
        ("gradient", _("Gradient Horizontal")),
        ("gradient_vertical", _("Gradient Vertical")),
    )
    
    base_form_class = RasterStyleModelForm
    
    name = models.CharField(max_length=256, verbose_name=_("name"),
                            help_text=_("Style name for identification"))
    unit = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("data unit"),
                            help_text=_("Data unit"))
    min = models.IntegerField(default=0, verbose_name=_("minimum value"), help_text=_("minimum value"))
    max = models.IntegerField(default=100, verbose_name=_("maximum value"), help_text=_("maximum value"))
    steps = models.IntegerField(default=5, validators=[MinValueValidator(3), MaxValueValidator(20), ], null=True,
                                blank=True, verbose_name=_("steps"), help_text=_("Number of steps"))
    use_custom_colors = models.BooleanField(default=False, verbose_name=_("Use Custom Colors"))
    palette = models.TextField(blank=True, null=True, verbose_name=_("Color Palette"))
    interpolate = models.BooleanField(default=False, verbose_name=_("interpolate"), help_text="Interpolate colorscale")
    legend_type = models.CharField(max_length=100, choices=LEGEND_TYPE_CHOICES, default="choropleth_vertical",
                                   verbose_name=_("Legend Type"))
    custom_color_for_rest = ColorField(blank=True, null=True, default="#ff0000",
                                       verbose_name=_("Color for the rest of values"),
                                       help_text=_(
                                           "Color for values greater than the values defined above, "
                                           "as well as values greater than the maximum defined value"))
    
    class Meta:
        verbose_name = _("Raster Style")
        verbose_name_plural = _("Raster Styles")
    
    def __str__(self):
        return self.name
    
    panels = [
        FieldPanel("name"),
        FieldPanel("unit"),
        FieldRowPanel(
            [
                FieldPanel("min"),
                FieldPanel("max"),
            ], _("Data values")
        ),
        FieldPanel("steps"),
        FieldPanel("palette", widget=RasterStyleWidget),
        FieldPanel("legend_type"),
        FieldPanel("use_custom_colors"),
        MultiFieldPanel([
            InlinePanel("color_values", heading=_("Color Values"), label=_("Color Value")),
            NativeColorPanel("custom_color_for_rest"),
        ], _("Custom Color Values")),
    ]
    
    def get_palette_list(self):
        if not self.use_custom_colors:
            return self.palette.split(",")
        return self.get_custom_palette()
    
    @property
    def min_value(self):
        return self.min
    
    @property
    def max_value(self):
        max_value = self.max
        if self.min == max_value:
            max_value += 0.1
        return max_value
    
    @property
    def scale_value(self):
        return 254 / (self.max_value - self.min_value)
    
    @property
    def offset_value(self):
        return -self.min_value
    
    @property
    def clip_value(self):
        return self.max_value + self.offset_value
    
    @property
    def palette_legend_values(self):
        if self.use_custom_colors:
            return None
        
        colors = self.get_palette_list()
        step = (self.max - self.min) / (len(colors) - (2 if self.min > 0 else 1))
        precision = significant_digits(step, self.max)
        value_format = round_to_precision(precision)
        
        val_from = self.min
        val_to = value_format(self.min + step)
        
        items = []
        
        for i, color in enumerate(colors):
            item = {"color": color}
            
            if i == 0 and self.min > 0:
                item.update({
                    "from": 0,
                    "to": self.min,
                    "name": "< {}".format(self.min)
                })
                val_to = self.min
            
            elif val_from < self.max:
                item.update({
                    "from": round(val_from, 1),
                    "to": round(val_to, 1),
                    "name": "{} - {}".format(val_from, val_to)
                })
            else:
                item.update({
                    "from": val_from,
                    "name": "> {}".format(val_from)
                })
            
            val_from = val_to
            val_to = value_format(self.min + step * (i + (1 if self.min > 0 else 2)))
            
            items.append(item)
        
        return items
    
    def get_custom_color_values(self):
        values = []
        color_values = self.color_values.order_by('threshold')
        
        for i, c_value in enumerate(color_values):
            value = c_value.value
            # if not the first one, add prev value for later comparison
            if i == 0:
                value["min_value"] = None
            else:
                value["min_value"] = color_values[i - 1].threshold
            value["max_value"] = value["threshold"]
            values.append(value)
        
        return values
    
    def get_custom_palette(self):
        colors = []
        for i in range(256):
            color = self.get_color_for_index(i)
            colors.append(color)
        
        return colors
    
    def get_color_for_index(self, index_value):
        values = self.get_custom_color_values()
        
        for value in values:
            max_value = value["max_value"] + self.offset_value
            
            if max_value > self.clip_value:
                max_value = self.clip_value
            
            if max_value < 0:
                max_value = 0
            
            max_value = self.scale_value * max_value
            
            if value["min_value"] is None:
                if index_value <= max_value:
                    return values[0]["color"]
            
            if value["min_value"] is not None:
                min_value = value["min_value"] + self.offset_value
                
                if min_value > self.clip_value:
                    min_value = self.clip_value
                
                if min_value < 0:
                    min_value = 0
                
                min_value = self.scale_value * min_value
                
                if min_value < index_value <= max_value:
                    return value["color"]
        
        return self.custom_color_for_rest
    
    def get_style_as_json(self):
        palette = self.get_palette_list()
        style = {
            "bands": [
                {
                    "band": 1,
                    "min": self.min,
                    "max": self.max,
                    "palette": palette,
                    "scheme": "discrete",
                }
            ]
        }
        return style
    
    def get_color_ramp(self):
        """Return a renderer-friendly color ramp for client-side rasters (e.g. COG)."""
        if self.use_custom_colors:
            stops = [
                {"value": cv.threshold, "color": cv.color}
                for cv in self.color_values.order_by('threshold')
            ]
            return {
                "type": "step",
                "min": self.min,
                "max": self.max,
                "stops": stops,
                "restColor": self.custom_color_for_rest,
                "unit": self.unit,
            }

        palette = self.get_palette_list()
        if not palette or len(palette) < 2:
            return None

        n = len(palette)
        step = (self.max - self.min) / (n - 1)
        stops = [{"value": self.min + i * step, "color": color} for i, color in enumerate(palette)]
        return {
            "type": "interpolate" if self.interpolate else "step",
            "min": self.min,
            "max": self.max,
            "stops": stops,
            "unit": self.unit,
        }

    def get_legend_config(self):
        items = []
        legend_type = self.legend_type
        if self.use_custom_colors:
            values = self.get_custom_color_values()
            count = len(values)
            
            if count > 0:
                for value in values:
                    item = {
                        "name": "",
                        "color": value['color']
                    }
                    if value.get("show_on_legend"):
                        item.update({
                            "name": value['label'] if value.get('label') else value['threshold'],
                        })
                    items.append(item)
                
                # if only one item and it is the custom color for rest, then show it as basic legend
                # no matter what the legend type was set
                if count == 1 and items[0].get("color") == self.custom_color_for_rest:
                    legend_type = "basic"
                else:
                    rest_item = {"name": "", "color": self.custom_color_for_rest}
                    items.append(rest_item)
        else:
            items = self.palette_legend_values
        
        config = {"type": legend_type, "items": items, }
        
        if self.unit:
            config["units"] = self.unit
        return config


class ColorValue(TimeStampedModel, Orderable):
    layer = ParentalKey(RasterStyle, related_name='color_values')
    threshold = models.FloatField(verbose_name=_("Threshold value"), help_text=_(
        "Values less than or equal to the input value, will be assigned the chosen color"))
    color = ColorField(default="#ff0000", verbose_name=_("color"))
    show_on_legend = models.BooleanField(default=True, verbose_name=_("Show label on Legend"))
    label = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Optional Label'))
    
    class Meta:
        verbose_name = _("Color Value")
        verbose_name_plural = _("Color Values")
    
    panels = [
        FieldPanel("threshold"),
        NativeColorPanel("color"),
        FieldPanel("show_on_legend"),
        FieldPanel("label")
    ]
    
    @property
    def value(self):
        return {
            "threshold": self.threshold,
            "color": self.color,
            "label": self.label,
            "show_on_legend": self.show_on_legend
        }
