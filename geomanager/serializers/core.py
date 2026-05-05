from rest_framework import serializers

from geomanager.models import Category
from geomanager.models.core import SubCategory, Dataset, Metadata
from geomanager.serializers.raster_cog import RasterCOGLayerSerializer
from geomanager.serializers.raster_file import RasterFileLayerSerializer
from geomanager.serializers.raster_tile import RasterTileLayerSerializer
from geomanager.serializers.vector_file import VectorFileLayerSerializer
from geomanager.serializers.vector_tile import VectorTileLayerSerializer
from geomanager.serializers.wms import WmsLayerSerializer


class DatasetSerializer(serializers.ModelSerializer):
    layers = serializers.SerializerMethodField()
    layer = serializers.SerializerMethodField()
    dataset = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()
    isMultiLayer = serializers.SerializerMethodField()
    initialVisible = serializers.SerializerMethodField()

    class Meta:
        model = Dataset
        fields = ["id", "dataset", "name", "capabilities", "summary", "layer", "isMultiLayer", "category",
                  "sub_category", "metadata", "layers", "initialVisible", "public", "layer_type"]

    def get_initialVisible(self, obj):
        return obj.initial_visible

    def get_isMultiLayer(self, obj):
        return obj.multi_layer

    def get_capabilities(self, obj):
        return obj.capabilities

    def get_layers(self, obj):
        request = self.context.get('request')

        if obj.layer_type == "raster_file":
            return RasterFileLayerSerializer(obj.raster_file_layers, many=True, context={"request": request}).data

        if obj.layer_type == "vector_file":
            return VectorFileLayerSerializer(obj.vector_file_layers, many=True, context={"request": request}).data

        if obj.layer_type == "wms":
            return WmsLayerSerializer(obj.wms_layers, many=True, context={"request": request}).data

        if obj.layer_type == "raster_tile":
            return RasterTileLayerSerializer(obj.raster_tile_layers, many=True, context={"request": request}).data

        if obj.layer_type == "vector_tile":
            return VectorTileLayerSerializer(obj.vector_tile_layers, many=True, context={"request": request}).data

        if obj.layer_type == "raster_cog":
            return RasterCOGLayerSerializer(obj.raster_cog_layers, many=True, context={"request": request}).data

        return None

    def get_layer(self, obj):
        return obj.get_default_layer()

    def get_dataset(self, obj):
        return obj.id

    def get_name(self, obj):
        return obj.title


class SubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubCategory
        fields = "__all__"


class CategorySerializer(serializers.ModelSerializer):
    sub_categories = SubCategorySerializer(many=True, read_only=True)
    icon = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'title', 'icon', 'active', 'public', 'sub_categories']

    def get_icon(self, obj):
        icon_name = obj.icon
        if not icon_name:
            icon_name = "layer-group"
        return f"icon-{icon_name}"


class MetadataSerialiazer(serializers.ModelSerializer):
    class Meta:
        model = Metadata
        fields = "__all__"
