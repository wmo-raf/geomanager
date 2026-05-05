from django.contrib.admin.utils import quote
from django.urls import reverse
from wagtail_modeladmin.helpers import AdminURLHelper


def get_layer_action_url(layer_type, action, action_args=None):
    if layer_type == "raster_file":
        from geomanager.models import RasterFileLayer
        file_layer_admin_helper = AdminURLHelper(RasterFileLayer)
        url = file_layer_admin_helper.get_action_url(action, action_args)
    elif layer_type == "vector_file":
        from geomanager.models.vector_file import VectorFileLayer
        vector_layer_admin_helper = AdminURLHelper(VectorFileLayer)
        url = vector_layer_admin_helper.get_action_url(action, action_args)
    elif layer_type == "wms":
        from geomanager.models.wms import WmsLayer
        wms_layer_admin_helper = AdminURLHelper(WmsLayer)
        url = wms_layer_admin_helper.get_action_url(action, action_args)
    elif layer_type == "raster_tile":
        from geomanager.models.raster_tile import RasterTileLayer
        raster_tile_layer_admin_helper = AdminURLHelper(RasterTileLayer)
        url = raster_tile_layer_admin_helper.get_action_url(action, action_args)
    elif layer_type == "vector_tile":
        from geomanager.models.vector_tile import VectorTileLayer
        vector_tile_layer_admin_helper = AdminURLHelper(VectorTileLayer)
        url = vector_tile_layer_admin_helper.get_action_url(action, action_args)
    elif layer_type == "raster_cog":
        from geomanager.models.raster_cog import RasterCOGLayer
        raster_cog_layer_admin_helper = AdminURLHelper(RasterCOGLayer)
        url = raster_cog_layer_admin_helper.get_action_url(action, action_args)
    else:
        url = None

    return url


def get_preview_url(layer_type, dataset_id, layer_id=None):
    args = [quote(dataset_id)]
    if layer_id:
        args.append(layer_id)

    if layer_type == "raster_file":
        if layer_id:
            preview_url = reverse(
                f"geomanager_preview_raster_layer",
                args=args,
            )
        else:
            preview_url = reverse(
                f"geomanager_preview_raster_dataset",
                args=args,
            )
    elif layer_type == "vector_file":
        if layer_id:
            preview_url = reverse(
                f"geomanager_preview_vector_layer",
                args=args,
            )
        else:
            preview_url = reverse(
                f"geomanager_preview_vector_dataset",
                args=args,
            )

    elif layer_type == "wms":
        if layer_id:
            preview_url = reverse(
                f"geomanager_preview_wms_layer",
                args=args,
            )
        else:
            preview_url = reverse(
                f"geomanager_preview_wms_dataset",
                args=args,
            )
    elif layer_type == "vector_tile":
        if layer_id:
            preview_url = reverse(
                f"geomanager_preview_vector_tile_layer",
                args=args,
            )
        else:
            preview_url = reverse(
                f"geomanager_preview_vector_tile_dataset",
                args=args,
            )
    elif layer_type == "raster_tile":
        if layer_id:
            preview_url = reverse(
                f"geomanager_preview_raster_tile_layer",
                args=args,
            )
        else:
            preview_url = reverse(
                f"geomanager_preview_raster_tile_dataset",
                args=args,
            )

    else:
        preview_url = None

    return preview_url


def get_upload_url(layer_type, dataset_id, layer_id=None):
    args = [quote(dataset_id)]
    if layer_id:
        args.append(layer_id)

    if layer_type == "raster_file":
        if layer_id:
            upload_url = reverse(
                f"geomanager_dataset_layer_upload_raster",
                args=args,
            )
        else:
            upload_url = reverse(
                f"geomanager_dataset_upload_raster",
                args=args,
            )
    elif layer_type == "vector_file":
        if layer_id:
            upload_url = reverse(
                f"geomanager_dataset_layer_upload_vector",
                args=args,
            )
        else:
            upload_url = reverse(
                f"geomanager_dataset_upload_vector",
                args=args,
            )
    else:
        upload_url = None

    return upload_url


def get_raster_layer_files_url(layer_id=None):
    from geomanager.models import LayerRasterFile
    admin_helper = AdminURLHelper(LayerRasterFile)
    url = admin_helper.get_action_url("index")

    if layer_id:
        url = url + f"?layer__id__exact={str(layer_id)}"

    return url


def get_vector_layer_files_url(layer_id=None):
    from geomanager.models import PgVectorTable
    admin_helper = AdminURLHelper(PgVectorTable)
    url = admin_helper.get_action_url("index")

    if layer_id:
        url = url + f"?layer__id__exact={str(layer_id)}"

    return url
