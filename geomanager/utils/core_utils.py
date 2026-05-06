from geomanager.models.core import Category, SubCategory


def create_category(title, order=None, icon=None, active=True, public=True, **extra):
    """
    Create (or update) a ``Category`` and persist its ordering.

    The ``order`` field is added by ``wagtail_adminsortable.AdminSortable``;
    it is left ``NULL`` by default and only filled when the user reorders rows
    via drag-and-drop in the Wagtail admin. When importing categories from a
    JSON catalog we want the catalog order to be the source of truth, so this
    helper exposes ``order`` as an explicit parameter.

    ``order`` is keyed against ``title`` via ``update_or_create`` so the
    importer is idempotent.
    """
    defaults = {
        "icon": icon,
        "active": active,
        "public": public,
        **extra,
    }
    if order is not None:
        defaults["order"] = order

    category, _ = Category.objects.update_or_create(title=title, defaults=defaults)
    return category


def create_sub_category(category, title, order=None, active=True, public=True, **extra):
    """
    Create (or update) a ``SubCategory`` under ``category`` with explicit ordering.

    ``SubCategory`` inherits from ``wagtail.models.Orderable`` so its order
    column is ``sort_order`` (not ``order`` like ``Category``). The caller
    passes a unified ``order`` parameter and we map it to ``sort_order``.
    """
    defaults = {
        "active": active,
        "public": public,
        **extra,
    }
    if order is not None:
        defaults["sort_order"] = order

    sub_category, _ = SubCategory.objects.update_or_create(
        category=category, title=title, defaults=defaults
    )
    return sub_category
