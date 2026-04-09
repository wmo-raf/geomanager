$((async function () {
    // default map style
    const defaultStyle = {
        version: 8,
        sources: {
            "carto-light": {
                type: "raster",
                tiles: [
                    "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
                    "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
                    "https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
                    "https://d.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
                ],
            },
            wikimedia: {
                type: "raster",
                tiles: ["https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}.png"],
            },
        },
        layers: [
            {
                id: "carto-light-layer",
                source: "carto-light",
                type: "raster",
                minzoom: 0,
                maxzoom: 22,
            },
        ],
    };

    // --- Step 1: Get selected layer info ---
    const $layerSelect = $('#layer_select')
    const $timestampsWrapper = $('#timestamps_wrapper')
    const $timestampsSelect = $('#timestamps_select')

    const selectedLayerId = $layerSelect.val();
    const selectedLayer = selectedLayerId
        ? window.geomanager_opts.dataLayers.find(l => l.id === selectedLayerId)
        : null;

    // --- Step 2: If PMTiles, load header to get bounds/center/zoom ---
    let mapOptions = {center: [0, 0], zoom: 2};
    let pmtilesInstance = null;

    if (selectedLayer) {
        const {layerConfig: {source}} = selectedLayer;
        const isPmtiles = !!source.url;

        if (isPmtiles) {
            // Register PMTiles protocol
            const pmtilesProtocol = new pmtiles.Protocol();
            maplibregl.addProtocol('pmtiles', pmtilesProtocol.tile);

            // Extract actual URL from "pmtiles://https://..." format
            const actualUrl = source.url.replace('pmtiles://', '');
            pmtilesInstance = new pmtiles.PMTiles(actualUrl);

            try {
                const header = await pmtilesInstance.getHeader();
                mapOptions.center = [header.centerLon, header.centerLat];
                mapOptions.zoom = header.centerZoom;

                if (header.minLon !== undefined && header.maxLon !== undefined) {
                    mapOptions.bounds = [
                        [header.minLon, header.minLat],
                        [header.maxLon, header.maxLat]
                    ];
                }
            } catch (e) {
                console.warn('Failed to read PMTiles header, using defaults:', e);
            }
        }
    }

    // --- Step 3: Build the map ---
    const initOptions = {
        container: "preview-map",
        style: defaultStyle,
        center: mapOptions.center,
        zoom: mapOptions.zoom,
        attributionControl: true,
    };

    if (mapOptions.bounds) {
        initOptions.bounds = mapOptions.bounds;
        initOptions.fitBoundsOptions = {padding: 20};
    }

    const map = new maplibregl.Map(initOptions);

    // add navigation control
    const navControl = new maplibregl.NavigationControl({
        showCompass: false
    })
    map.addControl(navControl, 'bottom-right')

    // wait for map to load
    await new Promise((resolve) => map.on("load", resolve));

    // load icon images
    const iconImages = window.geomanager_opts.iconImages

    if (iconImages) {
        iconImages.forEach(iconImage => {
            map.loadImage(iconImage.url, (error, image) => {
                if (error) throw error;
                map.addImage(iconImage.name, image);
            })
        })
    }

    // --- Helpers ---

    const updateTileUrl = (tileUrl, params) => {
        const url = new URL(tileUrl)
        const qs = new URLSearchParams(url.search);
        Object.keys(params).forEach(key => {
            qs.set(key, params[key])
        })
        url.search = decodeURIComponent(qs);
        return decodeURIComponent(url.href)
    }

    const fetchTimestamps = (tileJsonUrl, timestampResponseObjectKey = "timestamps") => {
        return fetch(tileJsonUrl).then(res => res.json()).then(res => res[timestampResponseObjectKey])
    }

    const setLayer = (selectedLayer) => {
        const {id, layerConfig: {source, render}, paramsSelectorConfig} = selectedLayer
        const isPmtiles = !!source.url

        const selectedTimestamp = $timestampsSelect.val()

        if (render && render.layers && !!render.layers.length) {

            render.layers.forEach((layer, index) => {

                const layerId = `${id}-${layer.type}-${index}`

                if (map.getLayer(layerId)) {
                    map.removeLayer(layerId);
                }

                if (map.getSource(layerId)) {
                    map.removeSource(layerId);
                }
                if (isPmtiles) {
                    map.addSource(layerId, {
                        type: "vector",
                        url: source.url,
                    });
                } else {
                    const params = {}

                    const timeConfig = paramsSelectorConfig && paramsSelectorConfig.find(c => c.key === "time" && c.type === "datetime") || {}
                    const {url_param} = timeConfig

                    if (url_param && selectedTimestamp) {
                        params[url_param] = selectedTimestamp
                    }

                    const tilesUrl = updateTileUrl(source.tiles[0], params)
                    map.addSource(layerId, {
                        type: "vector",
                        tiles: [tilesUrl],
                    });
                }

                map.addLayer({
                    id: layerId,
                    source: layerId,
                    ...layer
                });

                map.on('click', layerId, function (e) {

                    const popContent = featureHtml(e.features[0])
                    if (popContent) {
                        new maplibregl.Popup()
                            .setLngLat(e.lngLat)
                            .setHTML(popContent)
                            .addTo(map);
                    }
                });
            })
        }
    }

    const getPopupFields = () => {
        const selectedLayerId = $layerSelect.val();
        const selectedLayer = window.geomanager_opts.dataLayers.find(l => l.id === selectedLayerId)

        const {interactionConfig} = selectedLayer

        if (!interactionConfig) return null

        const {output} = interactionConfig

        if (!output) return null

        const fields = []

        output.forEach(o => {
            fields.push({name: o.column, label: o.property})
        })

        return fields
    }

    function featureHtml(f) {
        const p = f.properties;
        const popupFields = getPopupFields()

        if (!popupFields) return null

        const popupProps = Object.keys(p).reduce((all, key) => {
            if (popupFields.find(f => f.name === key)) {
                all[key] = p[key]
            }
            return all
        }, {})

        if (popupProps && !!Object.keys(popupProps).length) {
            let h = "<div class='station-popup-content'>";
            for (let k in popupProps) {
                const column = popupFields.find(f => f.name === k)
                h += "<p><b>" + `${column.label ? column.label : k}` + ":</b> " + popupProps[k] + "<br/></p>"
            }
            h += "</div>";
            return h
        }

        return null
    }

    // --- Event handlers ---
    $layerSelect.on("change", (e) => {
        const selectedLayerId = e.target.value;
    })

    const onTimeChange = (selectedTime, map, sourceId) => {
        const selectedLayerId = $layerSelect.val();
        const selectedLayer = window.geomanager_opts.dataLayers.find(l => l.id === selectedLayerId)
        setLayer(selectedLayer)
    };

    $timestampsSelect.on("change", (e) => {
        const selectedTime = e.target.value;
        const selectedLayerId = $layerSelect.val();
        onTimeChange(selectedTime, map, selectedLayerId);
    })

    // --- Initial layer load ---
    if (selectedLayer) {
        const {tileJsonUrl, timestampsResponseObjectKey} = selectedLayer

        if (tileJsonUrl) {
            const timestamps = await fetchTimestamps(tileJsonUrl, timestampsResponseObjectKey)
            $.each(timestamps, function (index, t) {
                const optionEl = new Option(t, t)
                $timestampsSelect.append(optionEl);
            });
            $timestampsWrapper.show()
        }

        setLayer(selectedLayer)
    }

}));
