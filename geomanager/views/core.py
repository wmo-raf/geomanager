from adminboundarymanager.models import AdminBoundarySettings
from django.urls import reverse
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from wagtail.api.v2.utils import get_full_url

from geomanager.models import Category, VectorLayerIcon, VectorTileLayerIcon, GeomanagerSettings
from geomanager.serializers import CategorySerializer


@api_view(['GET'])
@renderer_classes([JSONRenderer])
def get_mapviewer_config(request):
    gm_settings = GeomanagerSettings.for_request(request)
    abm_settings = AdminBoundarySettings.for_request(request)

    categories = Category.objects.all()
    categories_data = CategorySerializer(categories, many=True).data
    response = {
        "categories": categories_data,
        "enableMyAccount": False,
        "allowSignups": False,
    }

    if gm_settings.enable_my_account:
        response.update({
            "enableMyAccount": True,
        })

    if gm_settings.allow_signups:
        response.update({
            "allowSignups": True,
        })

    if gm_settings.map_disclaimer_text:
        response.update({"disclaimerText": gm_settings.map_disclaimer_text})

    links = {
        "mapViewerBaseUrl": get_full_url(request, (reverse("mapview"))),
    }

    if gm_settings.terms_of_service_page:
        links.update(
            {"termsOfServicePageUrl": get_full_url(request, gm_settings.terms_of_service_page.get_full_url(request))})

    if gm_settings.privacy_policy_page:
        links.update(
            {"privacyPolicyPageUrl": get_full_url(request, gm_settings.privacy_policy_page.get_full_url(request))})

    if gm_settings.map_disclaimer_page:
        links.update({"disclaimerPageUrl": gm_settings.map_disclaimer_page.get_full_url(request)})

    if gm_settings.contact_us_page:
        links.update({"contactUsPageUrl": gm_settings.contact_us_page.get_full_url(request)})

    response.update({"links": links})

    icon_images = []
    for icon in VectorLayerIcon.objects.all():
        icon_images.append({"name": icon.name, "url": get_full_url(request, icon.file.url)})

    for icon in VectorTileLayerIcon.objects.all():
        icon_images.append({"name": icon.name, "url": get_full_url(request, icon.file.url)})

    response.update({"vectorLayerIcons": icon_images})

    if gm_settings.logo:
        logo = {
            "imageUrl": get_full_url(request, gm_settings.logo.file.url)
        }

        if gm_settings.logo_page:
            logo.update({"linkUrl": get_full_url(request, gm_settings.logo_page.url)})

        if not gm_settings.logo_page and gm_settings.logo_external_link:
            logo.update({"linkUrl": gm_settings.logo_external_link, "external": True})

        response.update({"logo": logo})

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
                    data.update({"image": get_full_url(request, value.file.url)})

            data.update({"mapStyle": get_full_url(request, tile_gl_source.map_style_url)})
            base_maps_data.append(data)

    response.update({"basemaps": base_maps_data})

    nav_items = []
    if gm_settings.navigation:
        for menu_block in gm_settings.navigation:
            for item in menu_block.value:
                label = item.get("label")
                page = item.get("page")
                external_link = item.get("external_link")

                if not label:
                    continue

                if page and getattr(page, "url", None):
                    nav_items.append({
                        "label": label,
                        "url": get_full_url(request, page.url),
                        "external": False,
                    })
                elif external_link:
                    nav_items.append({
                        "label": label,
                        "url": external_link,
                        "external": True,
                    })

    response.update({"navigation": nav_items})

    return Response(response)
