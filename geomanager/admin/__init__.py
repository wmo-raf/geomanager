from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from wagtail.admin.menu import MenuItem, Menu
from wagtail_modeladmin.menus import GroupMenuItem
from wagtail_modeladmin.options import ModelAdminGroup

from geomanager.admin.boundary import urls as boundary_urls
from geomanager.admin.category import CategoryModelAdmin
from geomanager.admin.dataset import DatasetModelAdmin
from geomanager.admin.mbt_source import MBTSourceModelAdmin
from geomanager.admin.metadata import MetadataModelAdmin
from geomanager.admin.raster_cog import RasterCOGLayerModelAdmin, urls as raster_cog_urls
from geomanager.admin.raster_file import RasterFileLayerModelAdmin, RasterFileModelAdmin, urls as raster_file_urls
from geomanager.admin.raster_style import RasterStyleModelAdmin
from geomanager.admin.raster_tile import RasterTileLayerModelAdmin, urls as raster_tile_urls
from geomanager.admin.vector_file import VectorFileLayerModelAdmin, VectorTableModelAdmin, urls as vector_file_urls
from geomanager.admin.vector_tile import VectorTileLayerModelAdmin, urls as vector_tile_urls
from geomanager.admin.wms import WmsLayerModelAdmin, urls as wms_urls
from geomanager.models import GeomanagerSettings

urls = raster_file_urls \
       + raster_tile_urls \
       + raster_cog_urls \
       + vector_file_urls \
       + vector_tile_urls \
       + wms_urls \
       + boundary_urls


class ModelAdminGroupWithHiddenItems(ModelAdminGroup):
    def get_submenu_items(self):
        menu_items = []
        item_order = 1
        for model_admin in self.modeladmin_instances:
            if not model_admin.hidden:
                menu_items.append(model_admin.get_menu_item(order=item_order))
                item_order += 1
        return menu_items


class GeoManagerAdminGroup(ModelAdminGroupWithHiddenItems):
    menu_label = _('Geo Manager')
    menu_icon = 'layer-group'
    menu_order = 700
    items = (
        CategoryModelAdmin,
        DatasetModelAdmin,
        MetadataModelAdmin,
        RasterFileLayerModelAdmin,
        RasterCOGLayerModelAdmin,
        RasterStyleModelAdmin,
        VectorFileLayerModelAdmin,
        WmsLayerModelAdmin,
        RasterTileLayerModelAdmin,
        VectorTileLayerModelAdmin,
        MBTSourceModelAdmin,
        RasterFileModelAdmin,
        VectorTableModelAdmin
    )

    def get_menu_item(self):
        if self.modeladmin_instances:
            submenu = Menu(items=self.get_submenu_items(), register_hook_name='register_geo_manager_menu_item')
            return GroupMenuItem(self, self.get_menu_order(), submenu)

    def get_submenu_items(self):
        menu_items = super().get_submenu_items()

        boundary_loader = MenuItem(label=_("Map Boundaries"), url=reverse("boundary_landing"), icon_name="map")
        menu_items.append(boundary_loader)

        try:
            settings_url = reverse(
                "wagtailsettings:edit",
                args=[GeomanagerSettings._meta.app_label, GeomanagerSettings._meta.model_name, ],
            )
            gm_settings_menu = MenuItem(label=_("Settings"), url=settings_url, icon_name="cog")
            menu_items.append(gm_settings_menu)
        except Exception:
            pass

        return menu_items
