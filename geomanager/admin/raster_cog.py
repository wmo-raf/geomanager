from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from wagtail_modeladmin.helpers import AdminURLHelper
from wagtail_modeladmin.views import CreateView, EditView

from geomanager.admin.base import BaseModelAdmin, LayerIndexView, ModelAdminCanHide
from geomanager.models import Category, Dataset, RasterCOGLayer


class RasterCOGLayerCreateView(CreateView):
    def get_form(self):
        form = super().get_form()
        form.fields["dataset"].queryset = Dataset.objects.filter(layer_type="raster_cog")

        dataset_id = self.request.GET.get("dataset_id")
        if dataset_id:
            initial = {**form.initial}
            initial.update({"dataset": dataset_id})
            form.initial = initial
        return form

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        category_admin_helper = AdminURLHelper(Category)
        category_index_url = category_admin_helper.get_action_url("index")

        datasets_admin_helper = AdminURLHelper(Dataset)
        datasets_index_url = datasets_admin_helper.get_action_url("index")

        navigation_items = [
            {"url": category_index_url, "label": Category._meta.verbose_name_plural},
            {"url": datasets_index_url, "label": Dataset._meta.verbose_name_plural},
            {"url": "#", "label": _("New") + f" {RasterCOGLayer._meta.verbose_name}"},
        ]

        context_data.update({"navigation_items": navigation_items})
        return context_data


class RasterCOGLayerEditView(EditView):
    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        category_admin_helper = AdminURLHelper(Category)
        category_index_url = category_admin_helper.get_action_url("index")

        datasets_admin_helper = AdminURLHelper(Dataset)
        datasets_index_url = datasets_admin_helper.get_action_url("index")

        layer_admin_helper = AdminURLHelper(RasterCOGLayer)
        layer_index_url = layer_admin_helper.get_action_url("index")

        navigation_items = [
            {"url": category_index_url, "label": Category._meta.verbose_name_plural},
            {"url": datasets_index_url, "label": Dataset._meta.verbose_name_plural},
            {"url": layer_index_url, "label": RasterCOGLayer._meta.verbose_name_plural},
            {"url": "#", "label": self.instance.title},
        ]

        context_data.update({"navigation_items": navigation_items})
        return context_data


class RasterCOGLayerModelAdmin(BaseModelAdmin, ModelAdminCanHide):
    model = RasterCOGLayer

    index_template_name = "geomanager/modeladmin/index_without_custom_create.html"

    exclude_from_explorer = True
    hidden = True

    index_view_class = LayerIndexView
    create_view_class = RasterCOGLayerCreateView
    edit_view_class = RasterCOGLayerEditView

    def __init__(self, parent=None):
        super().__init__(parent)
        self.list_display = (list(self.list_display) or []) + ['dataset_link', "mapviewer_map_url"]
        self.dataset_link.__func__.short_description = _('Dataset')
        self.mapviewer_map_url.__func__.short_description = _("View on MapViewer")

    def mapviewer_map_url(self, obj):
        label = _("MapViewer")
        button_html = f"""
                <a href="{obj.mapviewer_map_url}" target="_blank" rel="noopener noreferrer" class="button button-small button--icon button-secondary">
                    <span class="icon-wrapper">
                        <svg class="icon icon-map icon" aria-hidden="true">
                            <use href="#icon-map"></use>
                        </svg>
                    </span>
                    {label}
                </a>
            """
        return mark_safe(button_html)

    def dataset_link(self, obj):
        button_html = f"""
            <a href="{obj.dataset.dataset_url()}">
                {obj.dataset.title}
            </a>
        """
        return mark_safe(button_html)


urls = []
