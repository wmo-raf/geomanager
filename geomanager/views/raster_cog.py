from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from geomanager.models import RasterCOGLayer


def raster_cog_as_tilejson(request, layer_id):
    layer = get_object_or_404(RasterCOGLayer, pk=layer_id)
    return JsonResponse(layer.get_tile_json(request))
