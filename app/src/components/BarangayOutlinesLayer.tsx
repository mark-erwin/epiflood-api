import { useEffect } from 'react';
import type OLMap from 'ol/Map';
import type { ObjectEvent } from 'ol/Object';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import GeoJSON from 'ol/format/GeoJSON';
import { Fill, Stroke, Style, Text } from 'ol/style';
import type { FeatureLike } from 'ol/Feature';

interface Props {
    map: OLMap;
    api: string;
}

// Possible names of the pcode field on the barangay GeoJSON. The first one found is used.
// Add yours here if it isn't in the list.
const PCODE_PROPS = ['barangay_pcode', 'pcode', 'PCODE', 'adm4_pcode', 'ADM4_PCODE'];

// Outline only: no fill, so it never hides the flood layer or the circles under/over it.
const outline = new Stroke({ color: 'rgba(71, 85, 105, 0.7)', width: 0.5 });
const baseStyle = new Style({ stroke: outline });

// Show barangay names only when zoomed in far enough to read them.
const LABEL_MIN_ZOOM = 10;

// True if a cluster circle already labels this barangay.
function hasCluster(feature: FeatureLike, keys: Set<string>): boolean {
    for (const prop of PCODE_PROPS) {
        const v = feature.get(prop);
        if (v !== undefined && v !== null) {
            return keys.has(`pcode:${v}`);
        }
    }
    // No pcode field found on this feature: fall back to the name.
    const name = String(feature.get('name') ?? '').trim().toLowerCase();
    return name !== '' && keys.has(`name:${name}`);
}

function makeStyle(map: OLMap) {
    return (feature: FeatureLike): Style => {
        const zoom = map.getView().getZoom() ?? 0;
        if (zoom < LABEL_MIN_ZOOM) return baseStyle;

        // A cluster circle already shows this name, so skip the outline label.
        const keys = map.get('namedClusters') as Set<string> | undefined;
        if (keys && keys.size > 0 && hasCluster(feature, keys)) return baseStyle;

        return new Style({
            stroke: outline,
            text: new Text({
                text: feature.get('name') ?? '',
                font: '11px system-ui, sans-serif',
                fill: new Fill({ color: '#334155' }),
                stroke: new Stroke({ color: 'rgba(255,255,255,0.9)', width: 3 }),
                overflow: false,
            }),
        });
    };
}

export default function BarangayOutlinesLayer({ map, api }: Props) {
    useEffect(() => {
        const layer = new VectorLayer({
            zIndex: 10, // above the flood layer (5), below the case circles (20)
            source: new VectorSource({
                url: `${api}/map/barangays`,
                format: new GeoJSON({ featureProjection: 'EPSG:3857' }),
            }),
            style: makeStyle(map),
        });

        // Labels depend on zoom and on which barangays have circles, so redraw on either change.
        const view = map.getView();
        const onZoom = () => layer.changed();
        const onProp = (e: ObjectEvent) => {
            if (e.key === 'namedClusters') layer.changed();
        };
        view.on('change:resolution', onZoom);
        map.on('propertychange', onProp);

        map.addLayer(layer);
        return () => {
            view.un('change:resolution', onZoom);
            map.un('propertychange', onProp);
            map.removeLayer(layer);
            layer.dispose();
        };
    }, [map, api]);

    return null;
}