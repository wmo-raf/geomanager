import datetime
import json
import tempfile

from django.core.exceptions import ValidationError
from django.core.files import File
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.defaultfilters import filesizeformat
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django_large_image import tilesource
from large_image.exceptions import TileSourceXYZRangeError
from wagtail.admin.auth import user_passes_test, user_has_any_page_permission, permission_denied
from wagtail.contrib.modeladmin.helpers import AdminURLHelper
from wagtail.models import Site
from wagtail.snippets.permissions import get_permission_name

from layermanager.forms import LayerRasterFileForm
from layermanager.models import Dataset, RasterUpload, FileImageLayer, LayerRasterFile
from layermanager.models.core import LayerManagerSettings
from layermanager.models.raster import WmsLayer
from layermanager.serializers.raster import WmsLayerSerializer
from layermanager.utils import UUIDEncoder
from layermanager.utils.raster_utils import get_tile_source, read_raster_info, convert_upload_to_geotiff

ALLOWED_RASTER_EXTENSIONS = ["tif", "tiff", "geotiff", "nc"]


@user_passes_test(user_has_any_page_permission)
def upload_raster_file(request, dataset_id=None, layer_id=None):
    permission = get_permission_name('change', Dataset)
    if not request.user.has_perm(permission):
        return permission_denied(request)

    site = Site.objects.get(is_default_site=True)
    layer_manager_settings = LayerManagerSettings.for_site(site)

    file_error_messages = {
        "invalid_file_extension": _(
            "Not a supported raster format. Supported formats: %(supported_formats)s."
        ) % {"supported_formats": ALLOWED_RASTER_EXTENSIONS},
        "file_too_large": _(
            "This file is too big (%(file_size)s). Maximum filesize %(max_filesize)s."
        ),
        "file_too_large_unknown_size": _(
            "This file is too big. Maximum filesize %(max_filesize)s."
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

    admin_url_helper = AdminURLHelper(Dataset)
    dataset_list_url = admin_url_helper.get_action_url("index")
    layer_list_url = None
    layer_preview_url = None

    if layer_id:
        layer = get_object_or_404(FileImageLayer, pk=layer_id)
        layer_admin_url_helper = AdminURLHelper(layer)
        layer_list_url = layer_admin_url_helper.get_action_url("index") + f"?dataset__id__exact={dataset.pk}"
        layer_preview_url = layer.preview_url

    context.update({
        "dataset": dataset,
        "layer": layer,
        "datasets_index_url": dataset_list_url,
        "layers_index_url": layer_list_url,
        "dataset_preview_url": dataset.preview_url,
        "layer_preview_url": layer_preview_url
    })

    # Check if user is submitting
    if request.method == 'POST':
        files = request.FILES.getlist('files[]', None)
        file = files[0]

        upload = RasterUpload.objects.create(file=file, dataset=dataset)

        raster_metadata = read_raster_info(upload.file.path)

        upload.raster_metadata = raster_metadata
        upload.save()

        query_set = FileImageLayer.objects.filter(dataset=dataset)

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
            "publish_action": reverse("layermanager_publish_raster", args=[upload.pk]),
            "delete_action": reverse("layermanager_delete_raster_upload", args=[upload.pk]),
        }

        response = {
            "success": True,
        }

        # we have more than one layer, render multiple forms
        if layer_forms:
            forms = []
            for form in layer_forms:
                ctx.update({**form})
                forms.append(render_to_string(
                    "raster_edit_form.html",
                    ctx,
                    request=request,
                ))
            response.update({"forms": forms})
        else:
            ctx.update({"form": layer_form})
            form = render_to_string(
                "raster_edit_form.html",
                ctx,
                request=request,
            )
            response.update({"form": form})

        return JsonResponse(response)

    return render(request, 'raster_upload.html', context)


@user_passes_test(user_has_any_page_permission)
def publish_raster(request, upload_id):
    if request.method != 'POST':
        return JsonResponse({"message": "Only POST allowed"})

    upload = RasterUpload.objects.get(pk=upload_id)

    if not upload:
        return JsonResponse({"message": "upload not found"}, status=404)

    db_layer = get_object_or_404(FileImageLayer, pk=request.POST.get('layer'))

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

    queryset = FileImageLayer.objects.filter(dataset=upload.dataset)
    layer_form = LayerRasterFileForm(data=data, queryset=queryset, **form_kwargs)

    ctx = {
        "dataset": upload.dataset,
        "publish_action": reverse("layermanager_publish_raster", args=[upload.pk]),
        "delete_action": reverse("layermanager_delete_raster_upload", args=[upload.pk]),
        "form": layer_form
    }

    def get_response():
        return {
            "success": False,
            "form": render_to_string(
                "raster_edit_form.html",
                ctx,
                request=request,
            ),
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
                    d_time = timezone.make_aware(d_time, timezone.get_current_timezone())

                    exists = LayerRasterFile.objects.filter(layer=db_layer, time=d_time).exists()

                    if exists:
                        layer_form.add_error("nc_dates",
                                             f"File with date {time_str} already exists for layer {db_layer}")
                        return JsonResponse(get_response())

                    with tempfile.NamedTemporaryFile(suffix=".tif") as f:
                        convert_upload_to_geotiff(upload, f, band_index=str(index), data_variable=nc_data_variable)
                        with open(f.name, mode='rb') as file:
                            file_content = File(file)
                            raster = LayerRasterFile(layer=layer, time=d_time)
                            raster.file.save(f"{time_str}.tif", file_content)
                            raster.save()
                except Exception as e:
                    layer_form.add_error(None, "Error occurred. Try again")
                    return JsonResponse(get_response())
            # cleanup upload
            upload.delete()
            return JsonResponse({"success": True, })
        elif nc_data_variable:
            exists = LayerRasterFile.objects.filter(layer=db_layer, time=time).exists()

            if exists:
                layer_form.add_error("time", f"File with date {time.isoformat()} already exists for layer {db_layer}")
                return JsonResponse(get_response())

            with tempfile.NamedTemporaryFile(suffix=".tif") as f:
                convert_upload_to_geotiff(upload, f, data_variable=nc_data_variable)
                with open(f.name, mode='rb') as file:
                    file_content = File(file)
                    raster = LayerRasterFile(layer=layer, time=time)
                    raster.file.save(f"{nc_data_variable}_{time.isoformat()}.tif", file_content)
                    raster.save()
            # cleanup upload
            upload.delete()
            return JsonResponse({"success": True, })
        else:
            exists = LayerRasterFile.objects.filter(layer=db_layer, time=time).exists()

            if exists:
                layer_form.add_error("time", f"File with date {time} already exists for selected layer")
                return JsonResponse(get_response())

            LayerRasterFile.objects.create(layer=layer, time=time, file=File(upload.file))

        # cleanup upload
        upload.delete()
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
        return JsonResponse({"message": "Only POST allowed"})

    upload = RasterUpload.objects.filter(pk=upload_id)

    if upload.exists():
        upload.first().delete()
    else:
        return JsonResponse({"success": True})

    return JsonResponse({"success": True, "layer_raster_file_id": upload_id, })


class RasterTileView(View):
    # TODO: Validate style query param thoroughly. If not validated, the whole app just exits without warning.
    # TODO: Cache getting layer style. We should not ne querying the database each time for style
    def get(self, request, z, x, y):
        layer_id = request.GET.get("layer")
        time = request.GET.get("time")
        fmt = request.GET.get("format", "png")
        projection = request.GET.get("projection", "EPSG:3857")
        style = request.GET.get("style", None)

        if layer_id is None:
            return HttpResponse("Missing layer query parameter", status=400)
        if time is None:
            return HttpResponse("Missing time query parameter", status=400)

        try:
            raster_file = LayerRasterFile.objects.filter(layer=layer_id, time=time)
        except Exception:
            return HttpResponse(f"File not found matching 'layer': {layer_id} and 'time': {time} ",
                                status=404)

        if not raster_file.exists():
            return HttpResponse(f"File not found matching 'layer': {layer_id} and 'time': {time} ",
                                status=404)

        if raster_file.exists():
            raster_file = raster_file.first()

        if style:
            # explict request to use layer defined style. Mostly used for admin previews
            if style == "layer-style":
                layer_style = raster_file.layer.style
                if layer_style:
                    style = layer_style.get_style_as_json()
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
            "style": style
        }

        source = get_tile_source(path=raster_file.file, options=options)

        try:
            tile_binary = source.getTile(int(x), int(y), int(z))
        except TileSourceXYZRangeError as e:
            raise ValidationError(e)
        mime_type = source.getTileMimeType()

        return HttpResponse(tile_binary, content_type=mime_type)


@user_passes_test(user_has_any_page_permission)
def preview_raster_layers(request, dataset_id, layer_id=None):
    dataset = get_object_or_404(Dataset, pk=dataset_id)

    base_absolute_url = request.scheme + '://' + request.get_host()

    dataset_admin_helper = AdminURLHelper(Dataset)
    dataset_list_url = dataset_admin_helper.get_action_url("index")

    image_file_layer_admin_helper = AdminURLHelper(FileImageLayer)
    image_file_layer_list_url = image_file_layer_admin_helper.get_action_url("index")

    context = {
        "dataset": dataset,
        "selected_layer": layer_id,
        "datasets_index_url": dataset_list_url,
        "image_file_layer_list_url": image_file_layer_list_url,
        "file_raster_api_base_url": request.build_absolute_uri("/api/file-raster"),
        "large_image_api_base_url": request.build_absolute_uri("/api/large-image"),
        "layer_tiles_url": base_absolute_url + "/api/raster-tiles/{z}/{x}/{y}",
    }

    return render(request, 'raster_preview.html', context)


@user_passes_test(user_has_any_page_permission)
def preview_wms_layers(request, dataset_id, layer_id=None):
    dataset = get_object_or_404(Dataset, pk=dataset_id)

    dataset_admin_helper = AdminURLHelper(Dataset)
    dataset_list_url = dataset_admin_helper.get_action_url("index")

    wms_layer_admin_helper = AdminURLHelper(WmsLayer)
    wms_layer_list_url = wms_layer_admin_helper.get_action_url("index")

    layer = None
    if layer_id:
        layer = WmsLayer.objects.get(pk=layer_id)

    dataset_layers = WmsLayerSerializer(dataset.wms_layers, many=True).data

    context = {
        "dataset": dataset,
        "selected_layer": layer,
        "datasets_index_url": dataset_list_url,
        "wms_layer_list_url": wms_layer_list_url,
        "dataset_layers": json.dumps(dataset_layers, cls=UUIDEncoder)
    }

    return render(request, 'wms_preview.html', context)