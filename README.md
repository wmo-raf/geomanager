# GeoManager

Wagtail based Geospatial Data Manager and backend CMS for [geomapviewer](https://github.com/wmo-raf/geomapviewer)

![Geomanager Admin Screenshot](./screenshots/geomanager_with_frontend.png)

# Background

Most national/regional institutions working in weather/climate/DRM sectors regularly produce and disseminate data and
information that is Geo-referenced. This can range from forecast model outputs, earth observation data, stations
observation, periodic bulletins and advisories and so on. Usually these are shared on their websites and social media
pages in static formats, mostly as PNGs or PDFS.

This is an effort to develop an interactive system for managing and publishing Geo-referenced (GIS)
datasets. As the institutions produce and share their products in static formats, they can also use packages like this,
to make their data interactive.

The package is developed primarily for use by NMHSs at national levels, but can be adapted in other institutions or
places that need to visualize their geospatial data.

# Features

All the raster and vector datasets uploaded must have time associated with each file.

For netCDF files with time dimension, time is automatically extracted from the file. For Geotiff, each uploaded file
must be manually assigned time.

Data management and visualization

- Uploading and visualization of gridded data
    - netCDF
    - Geotiff
- Uploading and visualization of vector data
    - Shapefiles
    - Geojson
- Raster Tile serving of raster data using [django-large-image](https://github.com/girder/django-large-image).
  All `django-large-image`features are available
- Vector tile serving using PostGIS MVT Tiles

MapViewer Management

- Management of layers visualized on the [geomapviewer](https://github.com/wmo-raf/geomapviewer)
    - Control on visibility (public or private) of layers on the MapViewer

# Installation

### Prerequisite

Before installing this package, you should make sure you have GDAL installed in your system.

`TIP:` Installing GDAL can be notoriously difficult. You can use pre-built Python wheels with the GDAL binary bundled,
provided by [KitWare](https://github.com/Kitware), for easy installation in production linux environments.

To install GDAL using KitWare GDAL wheel, use:

```shell
  pip install --find-links https://girder.github.io/large_image_wheels GDAL
```

Other required packages that you will need to install, if not installed already in your Wagtail Project

- psycopg2 - for postgres/postgis database connection

### Installation

You can install the package using pip:

```shell
pip install geomanager
```

Install this version of [wagtail-admin-sortable](https://github.com/wmo-raf/wagtail-admin-sortable) from Github. This
has some updates to the original packages.

```shell
pip install https://github.com/wmo-raf/wagtail-admin-sortable/archive/33bf22f290e7a4210b44667e9ff56e4b35ad309e.zip
````

# Usage

Make sure the following are all added to your `INSTALLED_APPS` in your Wagtail `settings`

````python
INSTALLED_APPS = [
    ...
    
    "geomanager",
    "adminboundarymanager",
    "django_large_image",
    'django_json_widget',
    'django_nextjs',
    "django_filters",
    "wagtail_color_panel",
    "wagtail_adminsortable",
    "wagtailhumanitarianicons",
    "wagtailiconchooser",
    "django_extensions",
    "wagtailfontawesomesvg"
    "allauth",
    "allauth.account",
    "wagtailcache",
    "wagtail_modeladmin"
    
    "wagtail.contrib.settings",
    "rest_framework",
    "django.contrib.gis",
    
    ...
]

````

Run migrations

```shell
python manage.py migrate geomanager
```

Add the following to your project's `urls.py`

```python
urlpatterns = [
    ...
    path("", include("geomanager.urls")),
    ...
]
```

# Wagtail Cache Setup

Geomanager depends on the [wagtail-cache](https://github.com/coderedcorp/wagtail-cache) package for caching requests.
Please have a look at the [wagtail-cache documentation](https://docs.coderedcorp.com/wagtail-cache/) for setup
instructions

# Including the Map Viewer

This package is the backend component to the frontend [geomapviewer](https://github.com/wmo-raf/geomapviewer).

# Documentation

TODO