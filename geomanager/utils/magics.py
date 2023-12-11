import os
from io import BytesIO

import PIL
import mercantile
import xarray as xr
from Magics import macro as magics

from . import TmpFile


def get_mxarray_data_from_geotiff(geotiff_path):
    # Open the geotiff
    ds = xr.open_dataset(geotiff_path, engine="rasterio")

    # Rename the x and y dimensions to longitude and latitude
    ds = ds.rename({'x': 'longitude', 'y': 'latitude'})
    ds.coords["longitude"].attrs = {
        "standard_name": "longitude",
    }
    ds.coords["latitude"].attrs = {
        "standard_name": "latitude",
    }

    # Select only the first band
    ds = ds.isel(band=0, drop=True)

    # Get the data as a mxarray
    data = magics.mxarray(ds, "band_data")

    return data


def get_magics_png_tile(source, x, y, z):
    # Get the web mercator bounding box of the tile
    bounds = mercantile.xy_bounds(x, y, z)

    # Get the data from the geotiff
    data = get_mxarray_data_from_geotiff(source.dataset.name)

    # width and height always 256
    width = 256
    height = 256

    # magics speaks in cm
    width_cm = width / 40.0
    height_cm = height / 40.0

    # subpage params
    mmap_params = {
        "subpage_map_projection": "EPSG:3857",
        "subpage_lower_left_latitude": bounds.bottom,
        "subpage_lower_left_longitude": bounds.left,
        "subpage_upper_right_latitude": bounds.top,
        "subpage_upper_right_longitude": bounds.right,
        "subpage_coordinates_system": "projection",  # we are using a defined projection
        "subpage_frame": "off",
        "page_x_length": width_cm,
        "page_y_length": height_cm,
        "super_page_x_length": width_cm,
        "super_page_y_length": height_cm,
        "subpage_x_length": width_cm,
        "subpage_y_length": height_cm,
        "subpage_x_position": 0.0,
        "subpage_y_position": 0.0,
        "output_width": width,
        "page_frame": "off",
        "skinny_mode": "on",
        "page_id_line": "off",
        "subpage_gutter_percentage": 0.,
    }

    # create area
    area = magics.mmap(**mmap_params)

    # create contour
    contour = magics.mcont(contour_automatic_setting="ecmwf", contour_style_name="sh_all_f05t300lst")

    output = TmpFile()
    output_fname = output.target("png")
    path, _ = os.path.splitext(output_fname)

    # create output
    moutput = magics.output(
        output_formats=['png'],
        output_name_first_page_number="off",
        output_cairo_transparent_background=True,
        output_width=width,
        output_name=path,
    )

    try:
        magics.plot(moutput, area, data, contour)
    except Exception as e:
        raise

    image = PIL.Image.open(output_fname)
    buffer = BytesIO()
    image.save(buffer, format="png")

    image_binary = buffer.getvalue()

    return image_binary
