from rest_framework import serializers

from geomanager.models import RasterCOGLayer


class RasterCOGLayerSerializer(serializers.ModelSerializer):
    layerConfig = serializers.SerializerMethodField()
    params = serializers.SerializerMethodField()
    paramsSelectorConfig = serializers.SerializerMethodField()
    legendConfig = serializers.SerializerMethodField()
    colorRamp = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    layerType = serializers.SerializerMethodField()
    multiTemporal = serializers.SerializerMethodField()
    currentTimeMethod = serializers.SerializerMethodField()
    autoUpdateInterval = serializers.SerializerMethodField()
    isMultiLayer = serializers.SerializerMethodField()
    nestedLegend = serializers.SerializerMethodField()
    canClip = serializers.SerializerMethodField()
    tileJsonUrl = serializers.SerializerMethodField()
    isDefault = serializers.SerializerMethodField()
    linkedLayers = serializers.SerializerMethodField()
    showAllMultiLayer = serializers.SerializerMethodField()

    class Meta:
        model = RasterCOGLayer
        fields = ["id", "dataset", "isDefault", "name", "layerType", "multiTemporal", "isMultiLayer", "legendConfig",
                  "colorRamp", "nestedLegend", "layerConfig", "params", "paramsSelectorConfig", "currentTimeMethod",
                  "autoUpdateInterval", "canClip", "tileJsonUrl", "linkedLayers", "showAllMultiLayer"]

    def get_linkedLayers(self, obj):
        return obj.linked_layers

    def get_showAllMultiLayer(self, obj):
        return obj.dataset.enable_all_multi_layers_on_add

    def get_isDefault(self, obj):
        return obj.default

    def get_isMultiLayer(self, obj):
        return obj.dataset.multi_layer

    def get_nestedLegend(self, obj):
        return obj.dataset.multi_layer

    def get_autoUpdateInterval(self, obj):
        return obj.dataset.auto_update_interval_milliseconds

    def get_multiTemporal(self, obj):
        return obj.dataset.multi_temporal

    def get_layerType(self, obj):
        return obj.dataset.layer_type

    def get_name(self, obj):
        return obj.title

    def get_layerConfig(self, obj):
        request = self.context.get('request')
        return obj.layer_config(request)

    def get_tileJsonUrl(self, obj):
        request = self.context.get('request')
        return obj.get_tile_json_url(request)

    def get_params(self, obj):
        return obj.params

    def get_paramsSelectorConfig(self, obj):
        return obj.param_selector_config

    def get_legendConfig(self, obj):
        return obj.get_legend_config()

    def get_colorRamp(self, obj):
        return obj.get_color_ramp()

    def get_currentTimeMethod(self, obj):
        return obj.dataset.current_time_method

    def get_canClip(self, obj):
        return obj.dataset.can_clip
