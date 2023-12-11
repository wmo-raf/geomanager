import datetime
import json
import tempfile
from typing import Optional, Any

import pytz
from adminboundarymanager.models import AdminBoundarySettings, AdminBoundary
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.files.base import File
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.defaultfilters import filesizeformat
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django_large_image import tilesource
from large_image.exceptions import TileSourceXYZRangeError
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from shapely import wkb
from wagtail.admin.auth import (
    user_passes_test,
    user_has_any_page_permission,
    permission_denied
)
from wagtail.api.v2.utils import get_full_url
from wagtail.models import Site
from wagtail.snippets.permissions import get_permission_name
from wagtail_modeladmin.helpers import AdminURLHelper
from wagtailcache.cache import cache_page

from geomanager.decorators import revalidate_cache
from geomanager.errors import RasterFileNotFound, QueryParamRequired, GeostoreNotFound
from geomanager.forms import LayerRasterFileForm
from geomanager.models import (
    Dataset,
    RasterUpload,
    RasterFileLayer,
    LayerRasterFile, Geostore
)
from geomanager.models.core import GeomanagerSettings, Category
from geomanager.serializers import RasterFileLayerSerializer
from geomanager.utils import UUIDEncoder
from geomanager.utils.magics import get_magics_png_tile
from geomanager.utils.raster_utils import (
    get_tile_source,
    read_raster_info,
    create_layer_raster_file,
    get_raster_pixel_data, get_geostore_data,
    check_raster_bounds_with_boundary,
    clip_netcdf, clip_geotiff,
    bounds_to_polygon
)

ALLOWED_RASTER_EXTENSIONS = ["tif", "tiff", "geotiff", "nc"]


@user_passes_test(user_has_any_page_permission)
def upload_raster_file(request, dataset_id=None, layer_id=None):
    permission = get_permission_name('change', Dataset)
    if not request.user.has_perm(permission):
        return permission_denied(request)

    edit_form_template = "geomanager/raster_file/raster_file_edit_form.html"

    site = Site.objects.get(is_default_site=True)
    layer_manager_settings = GeomanagerSettings.for_site(site)

    file_error_messages = {
        "invalid_file_extension": _(
            "Not a supported raster format. Supported formats: %(supported_formats)s."
        ) % {"supported_formats": ALLOWED_RASTER_EXTENSIONS},
        "file_too_large": _(
            "This file is too big (%(file_size)s). Maximum filesize %(max_filesize)s. "
            "You can adjust the Maximum upload file size under Geomanager settings"
        ),
        "file_too_large_unknown_size": _(
            "This file is too big. Maximum filesize %(max_filesize)s. "
            "You can adjust the Maximum upload file size under Geomanager settings."
        ) % {"max_filesize": filesizeformat(layer_manager_settings.max_upload_size_bytes)}}

    layer = None
    context = {}
    context.update(
        {
            "max_filesize": layer_manager_settings.max_upload_size_bytes,
            "allowed_extensions": ALLOWED_RASTER_EXTENSIONS,
            "error_max_file_size": file_error_messages["file_too_large_unknown_size"],
            "error_accepted_file_types": file_error_messages["invalid_file_extension"],
        }
    )

    dataset = get_object_or_404(Dataset, pk=dataset_id)

    category_admin_helper = AdminURLHelper(Category)
    categories_url = category_admin_helper.get_action_url("index")

    admin_url_helper = AdminURLHelper(Dataset)
    dataset_list_url = admin_url_helper.get_action_url("index")
    layer_list_url = None
    layer_preview_url = None

    if layer_id:
        layer = get_object_or_404(RasterFileLayer, pk=layer_id)
        layer_admin_url_helper = AdminURLHelper(layer)
        layer_list_url = layer_admin_url_helper.get_action_url("index") + f"?dataset__id__exact={dataset.pk}"
        layer_preview_url = layer.preview_url

    navigation_items = [
        {"url": categories_url, "label": Category._meta.verbose_name_plural},
        {"url": dataset_list_url, "label": Dataset._meta.verbose_name_plural},
        {"url": layer_list_url, "label": RasterFileLayer._meta.verbose_name_plural},
        {"url": "#", "label": _("Upload Raster Files")},
    ]

    context.update({
        "dataset": dataset,
        "layer": layer,
        "datasets_index_url": dataset_list_url,
        "layers_index_url": layer_list_url,
        "dataset_preview_url": dataset.preview_url,
        "layer_preview_url": layer_preview_url,
        "navigation_items": navigation_items,
    })

    gm_settings = GeomanagerSettings.for_request(request)

    crop_raster = gm_settings.crop_raster_to_country

    # Check if user is submitting
    if request.method == 'POST':
        files = request.FILES.getlist('files[]', None)
        upload_file = files[0]

        upload = RasterUpload.objects.create(file=upload_file, dataset=dataset)

        raster_metadata = read_raster_info(upload.file.path)

        abm_settings = AdminBoundarySettings.for_request(request)
        abm_extents = abm_settings.combined_countries_bounds
        abm_countries = abm_settings.countries_list

        if abm_extents and crop_raster and raster_metadata.get("bounds"):
            intersects_with_boundary, completely_inside_boundary = check_raster_bounds_with_boundary(
                raster_metadata.get("bounds"), abm_extents)

            # clipping raster to boundaries
            if not intersects_with_boundary:
                # no intersection. The raster is not within the set countries of interest
                return JsonResponse({
                    "success": False,
                    "error_message": _("You have set to clip uploaded raster files to the country(s) boundary but the"
                                       " uploaded file is not within the set countries. Make sure the uploaded file "
                                       "is within your country/countries or disable 'Crop raster to country' option "
                                       "in Geomanager settings")
                })

            elif not completely_inside_boundary:
                raster_driver = raster_metadata.get("driver")

                country_geoms = []
                for country in abm_countries:
                    code = country.get("code")
                    alpha3 = country.get("alpha3")

                    # query using code (2-letter code)
                    country_boundary = AdminBoundary.objects.filter(level=0, gid_0=code).first()

                    # query using alpha 3 (3-letter code)
                    if not country_boundary:
                        country_boundary = AdminBoundary.objects.filter(level=0, gid_0=alpha3).first()

                    if country_boundary:
                        shapely_geom = wkb.loads(country_boundary.geom.hex)
                        country_geoms.append(shapely_geom)
                    else:
                        # use bbox instead
                        bbox = country.get("bbox")
                        if bbox:
                            bounds_geom = bounds_to_polygon(bbox)
                            country_geoms.append(bounds_geom)

                union_polygon = country_geoms[0]
                for polygon in country_geoms[1:]:
                    union_polygon = union_polygon.union(polygon)

                if raster_driver == "netCDF":
                    clip_fn = clip_netcdf
                    suffix = ".nc"
                else:
                    clip_fn = clip_geotiff
                    suffix = ".tif"

                with tempfile.NamedTemporaryFile(suffix=suffix) as f:
                    clipped_raster = clip_fn(upload.file.path, union_polygon, f.name)
                    raster_metadata = read_raster_info(clipped_raster)

                    with open(clipped_raster, 'rb') as clipped_file:
                        file_obj = File(clipped_file, name=f.name)
                        upload.file.save(upload.file.name, file_obj, save=True)

        upload.raster_metadata = raster_metadata
        upload.save()

        query_set = RasterFileLayer.objects.filter(dataset=dataset)

        initial_data = {
            "layer": layer_id if layer_id else query_set.first()
        }

        form_kwargs = {}

        timestamps = raster_metadata.get("timestamps", None)

        if timestamps:
            form_kwargs.update({"nc_dates_choices": timestamps})
            initial_data.update({"nc_dates": timestamps})

        data_variables = raster_metadata.get("data_variables", None)

        layer_form = LayerRasterFileForm(queryset=query_set, initial=initial_data, **form_kwargs)
        layer_forms = []

        if data_variables and len(data_variables) > 0:
            for variable in data_variables:
                form_init_data = {**initial_data, "nc_data_variable": variable}
                l_form = LayerRasterFileForm(queryset=query_set, initial=form_init_data, **form_kwargs)
                layer_forms.append({"data_variable": variable, "form": l_form})

        ctx = {
            "dataset": dataset,
            "publish_action": reverse("geomanager_publish_raster", args=[upload.pk]),
            "delete_action": reverse("geomanager_delete_raster_upload", args=[upload.pk]),
        }

        response = {
            "success": True,
        }

        # we have more than one layer, render multiple forms
        if layer_forms:
            forms = []
            for form in layer_forms:
                ctx.update({**form})
                forms.append(render_to_string(edit_form_template, ctx, request=request, ))
            response.update({"forms": forms})
        else:
            ctx.update({"form": layer_form})
            form = render_to_string(edit_form_template, ctx, request=request)
            response.update({"form": form})

        return JsonResponse(response)

    return render(request, 'geomanager/raster_file/raster_file_upload.html', context)


@user_passes_test(user_has_any_page_permission)
def publish_raster(request, upload_id):
    if request.method != 'POST':
        return JsonResponse({"message": _("Only POST allowed")})

    upload = RasterUpload.objects.get(pk=upload_id)

    if not upload:
        return JsonResponse({"message": _("upload not found")}, status=404)

    db_layer = get_object_or_404(RasterFileLayer, pk=request.POST.get('layer'))

    raster_metadata = upload.raster_metadata

    form_kwargs = {}
    timestamps = raster_metadata.get("timestamps", None)

    data = {
        "layer": db_layer,
        "time": request.POST.get('time'),
        "nc_data_variable": request.POST.get('nc_data_variable')
    }

    if request.POST.get("nc_dates"):
        data.update({"nc_dates": request.POST.getlist("nc_dates")})

    if timestamps:
        form_kwargs.update({"nc_dates_choices": timestamps})

    queryset = RasterFileLayer.objects.filter(dataset=upload.dataset)
    layer_form = LayerRasterFileForm(data=data, queryset=queryset, **form_kwargs)

    ctx = {
        "dataset": upload.dataset,
        "publish_action": reverse("geomanager_publish_raster", args=[upload.pk]),
        "delete_action": reverse("geomanager_delete_raster_upload", args=[upload.pk]),
        "form": layer_form
    }

    def get_response():
        return {
            "success": False,
            "form": render_to_string("geomanager/raster_file/raster_file_edit_form.html", ctx, request=request, ),
        }

    if layer_form.is_valid():
        layer = layer_form.cleaned_data['layer']
        time = layer_form.cleaned_data['time']
        nc_dates = layer_form.cleaned_data['nc_dates']
        nc_data_variable = layer_form.cleaned_data['nc_data_variable']

        if nc_dates:
            data_timestamps = raster_metadata.get("timestamps")

            for time_str in nc_dates:
                try:
                    index = data_timestamps.index(time_str)

                    d_time = datetime.datetime.fromisoformat(time_str)

                    # Make the datetime object timezone aware. We assume the time is in standard UTC
                    d_time = d_time.replace(tzinfo=pytz.UTC)

                    exists = LayerRasterFile.objects.filter(layer=db_layer, time=d_time).exists()

                    if exists:
                        error_message = _("File with date %(time_str)s already exists for layer %(db_layer)s") % {
                            "time_str": time_str, "db_layer": db_layer}
                        layer_form.add_error("nc_dates", error_message)
                        return JsonResponse(get_response())

                    create_layer_raster_file(layer, upload, time=d_time, band_index=str(index),
                                             data_variable=nc_data_variable)
                except Exception as e:
                    layer_form.add_error(None, _("Error occurred. Try again"))
                    return JsonResponse(get_response())
            return JsonResponse({"success": True, })
        elif nc_data_variable:
            exists = LayerRasterFile.objects.filter(layer=db_layer, time=time).exists()

            if exists:
                error_message = _("File with date %(time)s already exists for layer %(db_layer)s") % {
                    "time": time.isoformat(), "db_layer": db_layer}
                layer_form.add_error("time", error_message)
                return JsonResponse(get_response())

            create_layer_raster_file(layer, upload, time, data_variable=nc_data_variable)
            # cleanup upload
            return JsonResponse({"success": True, })
        else:
            exists = LayerRasterFile.objects.filter(layer=db_layer, time=time).exists()

            if exists:
                error_message = _("File with date %(time)s already exists for selected layer") % {
                    "time": time.isoformat()}
                layer_form.add_error("time", error_message)
                return JsonResponse(get_response())

            create_layer_raster_file(layer, upload, time)
        # cleanup upload
        return JsonResponse(
            {
                "success": True,
            }
        )
    else:
        return JsonResponse(get_response())


@user_passes_test(user_has_any_page_permission)
def delete_raster_upload(request, upload_id):
    if request.method != 'POST':
        return JsonResponse({"message": _("Only POST allowed")})

    upload = RasterUpload.objects.filter(pk=upload_id)

    if upload.exists():
        upload.first().delete()
    else:
        return JsonResponse({"success": True})

    return JsonResponse({"success": True, "layer_raster_file_id": upload_id, })


@user_passes_test(user_has_any_page_permission)
def preview_raster_layers(request, dataset_id, layer_id=None):
    dataset = get_object_or_404(Dataset, pk=dataset_id)

    base_absolute_url = get_full_url(request, "")

    category_admin_helper = AdminURLHelper(Category)
    categories_url = category_admin_helper.get_action_url("index")

    dataset_admin_helper = AdminURLHelper(Dataset)
    dataset_list_url = dataset_admin_helper.get_action_url("index") + f"?id={dataset_id}"

    raster_file_layer_admin_helper = AdminURLHelper(RasterFileLayer)
    raster_file_layer_list_url = raster_file_layer_admin_helper.get_action_url("index")
    raster_file_layer_list_url = raster_file_layer_list_url + f"?dataset__id__exact={dataset_id}"

    dataset_layers = RasterFileLayerSerializer(dataset.raster_file_layers, many=True, context={"request": request}).data

    selected_layer = None

    if layer_id:
        selected_layer = dataset.raster_file_layers.get(pk=layer_id)

    navigation_items = [
        {"url": categories_url, "label": Category._meta.verbose_name_plural},
        {"url": dataset_list_url, "label": Dataset._meta.verbose_name_plural},
        {"url": raster_file_layer_list_url, "label": RasterFileLayer._meta.verbose_name_plural},
        {"url": "#", "label": _("Preview")},
    ]

    context = {
        "dataset": dataset,
        "dataset_layers": json.dumps(dataset_layers, cls=UUIDEncoder),
        "selected_layer": selected_layer,
        "datasets_index_url": dataset_list_url,
        "image_file_layer_list_url": raster_file_layer_list_url,
        "file_raster_list_url": get_full_url(request, reverse("file-raster-list")),
        "large_image_color_maps_url": get_full_url(request, reverse("large-image-colormaps")),
        "file_raster_metadata_url": get_full_url(request, reverse("file-raster-metadata", args=("0",))),
        "base_absolute_url": base_absolute_url,
        "navigation_items": navigation_items,
    }
    return render(request, 'geomanager/raster_file/raster_file_layer_preview.html', context)


class RasterDataMixin:
    def get_raster_file_by_id(self, request: Request, file_id) -> LayerRasterFile:
        raster_file = LayerRasterFile.objects.filter(pk=file_id)

        if raster_file.exists():
            return raster_file.first()

        error_message = _("File not found matching 'id': %(file_id)s") % {"file_id": file_id}
        raise RasterFileNotFound(error_message)

    def get_single_raster_file(self, request: Request, layer_id) -> LayerRasterFile:
        time = self.get_query_param(request, "time")

        if not time:
            raise QueryParamRequired(_("time param required"))

        raster_file = LayerRasterFile.objects.filter(layer=layer_id, time=time)

        if raster_file.exists():
            return raster_file.first()

        error_message = _("File not found matching 'layer': %(layer_id)s and 'time': %(time)s") % {"layer_id": layer_id,
                                                                                                   "time": time}
        raise RasterFileNotFound(error_message)

    def get_multiple_raster_files(self, request: Request, layer_id) -> [LayerRasterFile]:
        time_from = self.get_query_param(request, "time_from")
        time_to = self.get_query_param(request, "time_to")

        if not time_from and not time_to:
            raise QueryParamRequired(_("time_from or time_to param required"))

        time_filter = {}

        if time_to and time_from:
            time_filter.update({"time__range": [time_from, time_to]})
        elif time_from:
            time_filter.update({"time__gte": time_from})
        else:
            time_filter.update({"time__lte": time_to})

        raster_files = LayerRasterFile.objects.filter(layer=layer_id, **time_filter)

        return raster_files

    def get_coords(self, request: Request):
        x_coord = self.get_query_param(request, "x")
        y_coord = self.get_query_param(request, "y")

        if not x_coord:
            raise QueryParamRequired(_("x param required"))

        if not y_coord:
            return QueryParamRequired(_("y param required"))

        x_coord = float(x_coord)
        y_coord = float(y_coord)

        return x_coord, y_coord

    def get_pixel_data(self, request: Request, layer_id):
        raster_file = self.get_single_raster_file(request, layer_id)
        x_coord, y_coord = self.get_coords(request)

        pixel_data = get_raster_pixel_data(raster_file.file, x_coord, y_coord)

        return {"date": raster_file.time, "value": pixel_data}

    def get_geostore(self, request: Request):
        geostore_id = self.get_query_param(request, "geostore_id")

        if not geostore_id:
            raise QueryParamRequired(_("geostore_id param required"))

        try:
            geostore = Geostore.objects.get(pk=geostore_id)
        except ObjectDoesNotExist:
            error_message = _("Geostore with id %(geostore_id)s does not exist") % {"geostore_id": geostore_id}
            raise GeostoreNotFound(error_message)
        return geostore

    def get_raster_geostore_data(self, raster_file, geostore, value_type):
        geostore_data = get_geostore_data(raster_file.file, geostore)

    def get_query_param(self, request: Request, key: str, default: Optional[Any] = '') -> str:
        return request.query_params.get(key, str(default))


@method_decorator(revalidate_cache, name='get')
@method_decorator(cache_page, name='get')
class RasterTileView(RasterDataMixin, APIView):
    # TODO: Validate style query param thoroughly. If not validated, the whole app just exits without warning.
    # TODO: Cache getting layer style. We should not be querying the database each time for style
    def get(self, request, layer_id, z, x, y):
        try:
            raster_file = self.get_single_raster_file(request, layer_id)
        except QueryParamRequired as e:
            return HttpResponse(e.message, status=400)
        except RasterFileNotFound as e:
            return HttpResponse(e, status=404)

        fmt = self.get_query_param(request, "format", "png")
        projection = self.get_query_param(request, "projection", "EPSG:3857")
        style = self.get_query_param(request, "style")
        geostore_id = self.get_query_param(request, "geostore_id")

        if style:
            # explict request to use layer defined style. Mostly used for admin previews
            if style == "layer-style":
                layer_style = raster_file.layer.style
                if layer_style:
                    style = layer_style.get_style_as_json()
                else:
                    style = None
            else:
                # try validating style
                # TODO: do more thorough validation
                try:
                    style = json.loads(style)
                except Exception:
                    style = None
        else:
            layer_style = raster_file.layer.style
            if layer_style:
                style = layer_style.get_style_as_json()

        encoding = tilesource.format_to_encoding(fmt, pil_safe=True)

        options = {
            "encoding": encoding,
            "projection": projection,
            "style": style,
            "geostore_id": geostore_id
        }

        source = get_tile_source(path=raster_file.file, options=options)
        mime_type = source.getTileMimeType()

        try:
            tile_binary = get_magics_png_tile(source, int(x), int(y), int(z))
            return HttpResponse(tile_binary, content_type=mime_type)
        except Exception as e:
            print(e, "Error", "Error")

        try:
            tile_binary = source.getTile(int(x), int(y), int(z))
        except TileSourceXYZRangeError as e:
            raise ValidationError(e)

        mime_type = source.getTileMimeType()

        return HttpResponse(tile_binary, content_type=mime_type)


@method_decorator(revalidate_cache, name='get')
@method_decorator(cache_page, name='get')
class RasterThumbnailView(RasterDataMixin, APIView):
    def get(self, request, file_id):
        try:
            raster_file = self.get_raster_file_by_id(request, file_id)
        except QueryParamRequired as e:
            return HttpResponse(e.message, status=400)
        except RasterFileNotFound as e:
            return HttpResponse(e, status=404)

        fmt = self.get_query_param(request, "format", "png")
        projection = self.get_query_param(request, "projection", "EPSG:3857")
        style = self.get_query_param(request, "style")
        width = int(self.get_query_param(request, 'width', 256))
        height = int(self.get_query_param(request, 'height', 256))

        if style:
            # explict request to use layer defined style. Mostly used for admin previews
            if style == "layer-style":
                layer_style = raster_file.layer.style
                if layer_style:
                    style = layer_style.get_style_as_json()
                else:
                    style = None
            else:
                # try validating style
                # TODO: do more thorough validation
                try:
                    style = json.loads(style)
                except Exception:
                    style = None
        else:
            layer_style = raster_file.layer.style
            if layer_style:
                style = layer_style.get_style_as_json()

        encoding = tilesource.format_to_encoding(fmt, pil_safe=True)

        options = {
            "encoding": encoding,
            "projection": projection,
            "style": style,
        }

        source = get_tile_source(path=raster_file.file, options=options)

        thumb_data, mime_type = source.getThumbnail(encoding=encoding, width=width, height=height)

        return HttpResponse(thumb_data, content_type=mime_type)


@method_decorator(revalidate_cache, name='get')
@method_decorator(cache_page, name='get')
class RasterDataPixelView(RasterDataMixin, APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request, layer_id):
        try:
            pixel_data = self.get_pixel_data(request, layer_id)
        except QueryParamRequired as e:
            return JsonResponse(e.serialize, status=400)
        except RasterFileNotFound as e:
            return JsonResponse({"message": "Raster file not found"}, status=404)

        return Response(pixel_data)


@method_decorator(revalidate_cache, name='get')
@method_decorator(cache_page, name='get')
class RasterDataPixelTimeseriesView(RasterDataMixin, APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request, layer_id):
        try:
            raster_files = self.get_multiple_raster_files(request, layer_id)
            x_coord, y_coord = self.get_coords(request)
        except QueryParamRequired as e:
            return JsonResponse(e.serialize, status=400)
        except RasterFileNotFound as e:
            return JsonResponse({"message": e}, status=404)

        timeseries_data = []

        for raster_file in raster_files:
            pixel_data = get_raster_pixel_data(raster_file.file, x_coord, y_coord)
            timeseries_data.append({"date": raster_file.time, "value": pixel_data})

        return Response(timeseries_data)


@method_decorator(revalidate_cache, name='get')
@method_decorator(cache_page, name='get')
class RasterDataGeostoreView(RasterDataMixin, APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request, layer_id):
        try:
            value_type = self.get_query_param(request, "value_type")
            geostore = self.get_geostore(request)
            raster_file = self.get_single_raster_file(request, layer_id)
            data = get_geostore_data(raster_file.file, geostore, value_type)
        except QueryParamRequired as e:
            return JsonResponse(e.serialize, status=400)
        except (RasterFileNotFound, GeostoreNotFound) as e:
            return JsonResponse({"message": e}, status=404)
        return Response(data)


@method_decorator(revalidate_cache, name='get')
@method_decorator(cache_page, name='get')
class RasterDataGeostoreTimeseriesView(RasterDataMixin, APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request, layer_id):
        try:
            value_type = self.get_query_param(request, "value_type")
            raster_files = self.get_multiple_raster_files(request, layer_id)
            geostore = self.get_geostore(request)
        except QueryParamRequired as e:
            return JsonResponse(e.serialize, status=400)
        except (RasterFileNotFound, GeostoreNotFound) as e:
            return JsonResponse({"message": e}, status=404)

        timeseries_data = []

        for raster_file in raster_files:
            data = get_geostore_data(raster_file.file, geostore, value_type)

            if value_type and data.get(value_type):
                data = data[value_type]
            else:
                data = data.get("mean")

            timeseries_data.append({"date": raster_file.time, "value": data})

        return Response(timeseries_data)


def raster_file_as_tile_json(request, layer_id):
    layer = get_object_or_404(RasterFileLayer, pk=layer_id)
    tile_json = layer.get_tile_json(request)
    return JsonResponse(tile_json)
