from geomanager.constants import MAPBOX_GL_STYLE_SPEC


def get_vector_render_layers(render_layers_stream_field, tiled=False):
    render_layers = []

    optional_keys = ["filter", "maxzoom", "minzoom"]

    for layer in render_layers_stream_field:
        data = layer.block.get_api_representation(layer.value)

        render_layer_type = layer.block_type
        if render_layer_type == "icon" or render_layer_type == "text":
            render_layer_type = "symbol"

        data.update({"type": render_layer_type})

        # set source layer
        source_layer = "default"
        if data.get("source_layer"):
            source_layer = data.get("source_layer")
            del data["source_layer"]

        data.update({"source-layer": source_layer})

        # remove optional keys if they do not have any value
        for key in optional_keys:
            if not data.get(key):
                data.pop(key, None)

        paint_defaults = MAPBOX_GL_STYLE_SPEC.get("PAINT_DEFAULTS", {})
        layout_defaults = MAPBOX_GL_STYLE_SPEC.get("LAYOUT_DEFAULTS", {})

        paint = {}
        for key, value in data.get("paint", {}).items():
            # Drop unset/empty optional fields. CharBlock(required=False) returns
            # None when unfilled, which then surfaces as "key": null in the JSON
            # — maplibre rejects that for array-typed fields (e.g. icon-offset).
            if value is None or value == "":
                continue
            default_spec_value = paint_defaults.get(key)
            #  if is equal to default value, no need to include it
            if default_spec_value == value:
                continue
            js_key = key.replace("_", "-")
            paint.update({js_key: value})

        layout = {}
        for key, value in data.get("layout", {}).items():
            if value is None or value == "":
                continue
            default_spec_value = layout_defaults.get(key)
            #  if is equal to default value, no need to include it
            if default_spec_value == value:
                continue
            js_key = key.replace("_", "-")
            layout.update({js_key: value})

        if bool(paint):
            data.update({"paint": paint})
        else:
            # nothing for paint. Just delete it
            data.pop("paint", None)

        if bool(layout):
            data.update({"layout": layout})
        else:
            # nothing for layout. Just delete it
            data.pop("layout", None)

        data.update({
            "metadata": {
                "position": "top",
            }
        })

        render_layers.append(data)

    return render_layers
