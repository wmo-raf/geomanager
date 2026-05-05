import logging

from wagtailcache.cache import clear_cache

from .aoi import *
from .boundary import *
from .core import *
from .geomanager_settings import *
from .geostore import *
from .profile import *
from .raster_cog import *
from .raster_file import *
from .raster_tile import *
from .tile_gl import *
from .vector_file import *
from .vector_tile import *
from .wms import *
from .raster_style import *

logger = logging.getLogger(__name__)


# clear wagtail cache on saving the following models
@receiver(post_save, sender=Category)
@receiver(post_save, sender=SubCategory)
@receiver(post_save, sender=Dataset)
@receiver(post_save, sender=Metadata)
@receiver(post_save, sender=GeomanagerSettings)
@receiver(post_save, sender=RasterFileLayer)
@receiver(post_save, sender=LayerRasterFile)
@receiver(post_save, sender=RasterCOGLayer)
@receiver(post_save, sender=RasterStyle)
@receiver(post_save, sender=WmsLayer)
@receiver(post_save, sender=MBTSource)
@receiver(post_save, sender=VectorFileLayer)
@receiver(post_save, sender=PgVectorTable)
@receiver(post_save, sender=AdditionalMapBoundaryData)
def handle_clear_wagtail_cache(sender, **kwargs):
    logging.info("[WAGTAIL_CACHE]: Clearing cache")
    clear_cache()
