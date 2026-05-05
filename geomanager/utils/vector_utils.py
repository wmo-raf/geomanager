import glob
import json
import os
import tempfile
import uuid
from subprocess import Popen, PIPE
from urllib.parse import unquote
from zipfile import ZipFile

import geopandas as gpd
from django.conf import settings as django_settings
from django.contrib.gis.db import models
from django.db import connection
from django.utils.translation import gettext as _

from geomanager.errors import (
    NoShpFound,
    NoShxFound,
    NoDbfFound,
    InvalidFile,
    InvalidGeomType,
    GeomValidationNotImplemented
)

POSTGRES_DATA_TYPES_DJANGO_FIELDS_MAPPING = {
    'smallint': models.SmallIntegerField,
    'integer': models.IntegerField,
    'bigint': models.BigIntegerField,
    'decimal': models.DecimalField,
    'numeric': models.DecimalField,
    'real': models.FloatField,
    'double precision': models.FloatField,
    'character varying': models.CharField,
    'character': models.CharField,
    'text': models.TextField,
    'date': models.DateField,
    'time': models.TimeField,
    'timestamp': models.DateTimeField,
    'timestamp with time zone': models.DateTimeField,
    'interval': models.DurationField,
    'boolean': models.BooleanField,
    "Point": models.PointField,
    "MultiPoint": models.MultiPointField,
}

GEOM_TYPES = {
    "POINT": "Point",
    "MULTIPOINT": "MultiPoint",
    "POLYGON": "Polygon",
    "MULTIPOLYGON": "MultiPolygon",
    "LINESTRING": "LineString",
    "MULTILINESTRING": "MultiLineString",
}


def ogr2pg(file_path, table_name, db_settings, srid=4326, overwrite=False):
    # construct db connection options from uri
    db_host = db_settings.get("host")
    db_port = db_settings.get("port")
    db_user = db_settings.get("user")
    db_password = db_settings.get("password")
    db_name = db_settings.get("name")
    # unquote incase encoded
    db_password = unquote(db_password)

    pg_service_schema = db_settings.get("pg_service_schema")

    # construct ogr2ogr command
    # notable option: -lco FID=gid  - Use custom fid column name. ogr by default gives ogc_fid. We use gid instead
    cmd = ["ogr2ogr", "-f", "PostgreSQL",
           f"PG:host={db_host} port={db_port} user={db_user} password={db_password} dbname={db_name}", file_path,
           "-nln", table_name, "-lco", f"FID=gid", "-lco", f"SCHEMA={pg_service_schema}", "-lco", "GEOMETRY_NAME=geom",
           "-nlt", "PROMOTE_TO_MULTI", "-lco", "PRECISION=NO"
           ]

    # overwrite existing
    if overwrite:
        cmd.append("-lco")
        cmd.append("OVERWRITE=YES")

    p1 = Popen(cmd, stdout=PIPE, stderr=PIPE)

    p1.stdout.close()

    stdout, stderr = p1.communicate()

    # TODO: Catch possible errors better
    if stderr:
        raise Exception(stderr)

    full_table_name = f"{pg_service_schema}.{table_name}"

    pg_table = {"table_name": full_table_name, "srid": srid}

    info = get_postgis_table_info(pg_service_schema, table_name)

    pg_table.update({**info})

    return pg_table


def extract_zipped_shapefile(shp_zip_path, out_dir):
    # unzip file
    with ZipFile(shp_zip_path, 'r') as zip_obj:
        for filename in zip_obj.namelist():
            # ignore __macosx files
            if not filename.startswith('__MACOSX/'):
                zip_obj.extract(filename, out_dir)

    # Use the first available shp
    shp = glob.glob(f"{out_dir}/*.shp") or glob.glob(f"{out_dir}/*/*.shp")

    if not shp:
        raise NoShpFound(_("No shapefile found in provided zip file"))

    shp_fn = os.path.splitext(shp[0])[0]
    shp_dir = os.path.dirname(shp_fn)

    files = [os.path.join(shp_dir, f) for f in os.listdir(shp_dir)]

    # check for .shx
    if f"{shp_fn}.shx" not in files:
        raise NoShxFound(_("No .shx file found in provided zip file"))

    # check for .dbf
    if f"{shp_fn}.dbf" not in files:
        raise NoDbfFound(_("No .dbf file found in provided zip file"))

    # return first shp path
    return shp[0]


def ogr_db_import(file_path, table_name, db_settings, overwrite=False, validate_geom_types=None):
    file_extension = os.path.splitext(file_path)[1]

    # handle shapefile
    if file_extension == ".zip":
        with tempfile.TemporaryDirectory() as tmpdir:
            shp = extract_zipped_shapefile(file_path, tmpdir)
            if validate_geom_types and isinstance(validate_geom_types, list):
                validate_vector_geom_type(shp, validate_geom_types, vector_format="shp")

            table_info = ogr2pg(shp, table_name, db_settings, overwrite=overwrite)

            return table_info

    # handle geojson
    if file_extension == ".geojson":
        table_info = ogr2pg(file_path, table_name, db_settings, overwrite=overwrite)
        return table_info

    # handle geopackage
    if file_extension == ".gpkg":
        table_info = ogr2pg(file_path, table_name, db_settings, overwrite=overwrite)
        return table_info

    raise InvalidFile(message=_('Unsupported file type'))


def create_layer_vector_file(layer, upload, time, table_name=None, description=None):
    """
    Publish a ``VectorUpload`` into a ``PgVectorTable`` attached to ``layer``.

    Mirrors ``raster_utils.create_layer_raster_file``: callers pass an upload
    that already has its file on disk (admin form upload, API, etc.) and this
    function handles the ``ogr_db_import`` + ``PgVectorTable.objects.create``
    + cleanup of the upload. Returns the created ``PgVectorTable``.
    """
    # Imported lazily to avoid a circular import at module load (models import
    # from utils, utils would otherwise import models).
    from geomanager.models.vector_file import PgVectorTable
    from geomanager.settings import geomanager_settings

    table_name = (table_name or f"vector_{uuid.uuid4().hex[:12]}").lower()

    db = django_settings.DATABASES['default']
    db_settings = {
        'host': db.get('HOST'),
        'port': db.get('PORT'),
        'user': db.get('USER'),
        'password': db.get('PASSWORD'),
        'name': db.get('NAME'),
        'pg_service_schema': geomanager_settings.get('vector_db_schema'),
    }

    info = ogr_db_import(upload.file.path, table_name, db_settings)

    pg_table = PgVectorTable.objects.create(
        layer=layer,
        time=time,
        table_name=table_name,
        full_table_name=info.get('table_name', table_name),
        description=description,
        properties=info.get('properties'),
        bounds=info.get('bounds'),
        geometry_type=info.get('geom_type'),
    )

    upload.delete()
    return pg_table


def get_postgis_table_info(schema, table_name):
    # Get all the column names with corresponding data types
    with connection.cursor() as cursor:
        columns_sql = f"""SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}' AND table_schema = '{schema}'
        """
        cursor.execute(columns_sql)
        results = cursor.fetchall()
        column_data_types = [{"name": row[0], "data_type": row[1]} for row in results if row[0] != "geom"]

        # Get the extents of all the data in the table
        extent_sql = f"SELECT ST_Extent(geom) FROM {schema}.{table_name}"
        cursor.execute(extent_sql)
        bbox_text = cursor.fetchone()[0]
        bbox_str = bbox_text.replace("BOX(", "").replace(")", "").replace(" ", ",").split(",")

        # Get the geometry type of the 'geom' column
        geom_sql = f"""SELECT GeometryType(geom)
        FROM {schema}.{table_name} LIMIT 1
        """
        cursor.execute(geom_sql)
        result = cursor.fetchone()[0]
        geometry_type = result.replace('ST_', '')

    return {
        'properties': column_data_types,
        'bounds': bbox_str,
        'geom_type': GEOM_TYPES[geometry_type],
    }


def drop_vector_table(table_name):
    with connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")


def create_feature_collection_from_geom(geom):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": json.loads(geom.geojson),
                "properties": {}
            }
        ]
    }


def validate_vector_geom_type(file_path, valid_geom_types, vector_format):
    if vector_format == "shp":
        gdf = gpd.read_file(file_path, layer=0)
        geom_types = gdf.geometry.geom_type.unique()

        for geom_type in geom_types:
            if geom_type not in valid_geom_types:
                error_message = _("Invalid geometry type. Expected one of %(valid_geom_types)s. Not %(geom_type)s") % {
                    "valid_geom_types": valid_geom_types, "geom_type": geom_type}
                raise InvalidGeomType(error_message)
    else:
        error_message = _("Geometry Type validation not implemented for format %(vector_format)s") % {
            "vector_format": vector_format}
        raise GeomValidationNotImplemented(error_message)


def get_model_field(pg_data_type):
    return POSTGRES_DATA_TYPES_DJANGO_FIELDS_MAPPING.get(pg_data_type)
