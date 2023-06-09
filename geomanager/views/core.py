from adminboundarymanager.models import AdminBoundarySettings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from wagtailcache.cache import cache_page

from geomanager.models import Category
from geomanager.models.core import GeomanagerSettings
from geomanager.serializers import CategorySerializer


@api_view(['GET'])
@cache_page
def get_mapviewer_config(request):
    gm_settings = GeomanagerSettings.for_request(request)
    abm_settings = AdminBoundarySettings.for_request(request)

    categories = Category.objects.all()
    categories_data = CategorySerializer(categories, many=True).data
    response = {
        "categories": categories_data,
    }

    if gm_settings.logo:
        response.update({"logo": request.build_absolute_uri(gm_settings.logo.file.url)})

    if abm_settings.countries_list:
        response.update({
            "countries": abm_settings.countries_list,
            "bounds": abm_settings.combined_countries_bounds,
            "boundaryDataSource": abm_settings.data_source
        })

    base_maps_data = []

    tile_gl_source = gm_settings.tile_gl_source

    if tile_gl_source:
        # get base maps
        for base_map in gm_settings.base_maps:
            data = base_map.block.get_api_representation(base_map.value)
            for key, value in base_map.value.items():
                if key == "image" and value:
                    data.update({"image": request.build_absolute_uri(value.file.url)})

            data.update({"mapStyle": request.build_absolute_uri(tile_gl_source.map_style_url)})
            base_maps_data.append(data)

    response.update({"basemaps": base_maps_data})

    return Response(response)
