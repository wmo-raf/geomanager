from rest_framework import serializers

from geomanager.models.wms import WmsLayer


class WmsLayerSerializer(serializers.ModelSerializer):
    layerConfig = serializers.SerializerMethodField()
    params = serializers.SerializerMethodField()
    paramsSelectorConfig = serializers.SerializerMethodField()
    legendConfig = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    getCapabilitiesUrl = serializers.SerializerMethodField()
    layerName = serializers.SerializerMethodField()
    layerType = serializers.SerializerMethodField()
    multiTemporal = serializers.SerializerMethodField()
    currentTimeMethod = serializers.SerializerMethodField()
    paramsSelectorColumnView = serializers.SerializerMethodField()
    autoUpdateInterval = serializers.SerializerMethodField()
    isMultiLayer = serializers.SerializerMethodField()
    nestedLegend = serializers.SerializerMethodField()
    analysisConfig = serializers.SerializerMethodField()
    moreInfo = serializers.SerializerMethodField()
    getCapabilitiesLayerName = serializers.SerializerMethodField()
    isDefault = serializers.SerializerMethodField()
    linkedLayers = serializers.SerializerMethodField()
    showAllMultiLayer = serializers.SerializerMethodField()
    styles = serializers.SerializerMethodField()

    class Meta:
        model = WmsLayer
        fields = ["id", "dataset", "isDefault", "name", "isMultiLayer", "nestedLegend", "layerType", "layerConfig",
                  "params", "paramsSelectorConfig", "paramsSelectorColumnView", "legendConfig", "getCapabilitiesUrl",
                  "layerName", "multiTemporal", "currentTimeMethod", "autoUpdateInterval", "analysisConfig", "moreInfo",
                  "getCapabilitiesLayerName", "linkedLayers", "showAllMultiLayer", "styles"]

    def get_showAllMultiLayer(self, obj):
        return obj.dataset.enable_all_multi_layers_on_add

    def get_linkedLayers(self, obj):
        return obj.linked_layers

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

    def get_currentTimeMethod(self, obj):
        return obj.dataset.current_time_method

    def get_layerType(self, obj):
        return obj.dataset.layer_type

    def get_name(self, obj):
        return obj.title

    def get_layerConfig(self, obj):
        layer_config = obj.layer_config

        return layer_config

    def get_params(self, obj):
        return obj.params

    def get_paramsSelectorConfig(self, obj):
        return obj.param_selector_config

    def get_paramsSelectorColumnView(self, obj):
        return not obj.params_selectors_side_by_side

    def get_legendConfig(self, obj):
        request = self.context.get('request')
        return obj.get_legend_config(request)

    def get_getCapabilitiesUrl(self, obj):
        return obj.get_capabilities_url

    def get_layerName(self, obj):
        return obj.layer_name

    def get_analysisConfig(self, obj):
        return obj.get_analysis_config()

    def get_moreInfo(self, obj):
        info = None
        for info in obj.more_info:
            info = info.value.as_dict
        return info

    def get_styles(self, obj):
        return [style.name for style in obj.wms_request_styles.all()]

    def get_getCapabilitiesLayerName(self, obj):
        if obj.get_capabilities_layer_name:
            return obj.get_capabilities_layer_name
        return None
