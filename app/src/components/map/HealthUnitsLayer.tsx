import { useEffect, useRef } from 'react';
import type OLMap from 'ol/Map';
import type BaseLayer from 'ol/layer/Base';
import type { FeatureLike } from 'ol/Feature';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import GeoJSON from 'ol/format/GeoJSON';
import { Fill, Icon, Stroke, Style, Text } from 'ol/style';
import { faHouseMedical } from '@fortawesome/free-solid-svg-icons';

// ---- Styling -------------------------------------------------------------

const MAX_CHARS = 18;
const MAX_LINES = 3;
const LABEL_MIN_ZOOM = 15;
const LABEL_MAX_RESOLUTION = 156543.03392804097 / 2 ** LABEL_MIN_ZOOM;

function wrapLabelText(text: string, maxChars = MAX_CHARS, maxLines = MAX_LINES): string {
    const lines: string[] = [];
    let line = '';

    for (const word of text.split(/\s+/).filter(Boolean)) {
        if (line && (line + ' ' + word).length > maxChars) {
            lines.push(line);
            line = word;
        } else {
            line = line ? `${line} ${word}` : word;
        }
    }
    if (line) lines.push(line);

    if (lines.length > maxLines) {
        const kept = lines.slice(0, maxLines);
        kept[maxLines - 1] = kept[maxLines - 1].replace(/\s*\S{0,2}$/, '') + '…';
        return kept.join('\n');
    }
    return lines.join('\n');
}

function fa_iconToDataURI(def: typeof faHouseMedical, color: string, size = 32): string {
    const [w, h, , , path] = def.icon;
    const d = Array.isArray(path) ? path.join(' ') : path;
    const svg =
        `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${w} ${h}">` +
        `<path fill="${color}" d="${d}"/></svg>`;
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

const iconStyle = new Style({
    image: new Icon({
        src: fa_iconToDataURI(faHouseMedical, '#54228D', 32),
        width: 16,
        height: 16,
        anchor: [0.5, 0.5],
    }),
});

const labelCache: Record<string, Style[]> = {};

function hospitalStyle(feature: FeatureLike, resolution: number): Style[] {
    if (resolution > LABEL_MAX_RESOLUTION) return [iconStyle];

    const name = String(feature.get('name') ?? '');
    return (labelCache[name] ??= [
        iconStyle,
        new Style({
            text: new Text({
                text: wrapLabelText(name),
                font: 'bold 12px "Montserrat", sans-serif',
                textAlign: 'center',
                offsetY: 32,
                fill: new Fill({ color: '#1f2937' }),
                stroke: new Stroke({ color: '#FBF8F3', width: 3 }),
            }),
        }),
    ]);
}

// ---- Layer ---------------------------------------------------------------

interface Props {
    map: OLMap;
    api: string;
    /** Show or hide the layer without refetching. Defaults to shown. */
    visible?: boolean;
}

export default function HealthUnitsLayer({ map, api, visible = true }: Props) {
    const layerRef = useRef<BaseLayer | null>(null);

    // Create the layer and fetch the data once per map/api.
    useEffect(() => {
        const source = new VectorSource();
        const layer = new VectorLayer({
            source,
            style: hospitalStyle,
            zIndex: 10, // above the flood layer (zIndex 5)
        });
        layerRef.current = layer;
        map.addLayer(layer);

        document.fonts.load('bold 12px "Montserrat"').then(() => layer.changed());

        const controller = new AbortController();
        (async () => {
            try {
                const res = await fetch(`${api}/map/health-units`, { signal: controller.signal });
                const data = await res.json();
                if (data?.features) {
                    const features = new GeoJSON().readFeatures(data, {
                        dataProjection: 'EPSG:4326',
                        featureProjection: 'EPSG:3857',
                    });
                    features.forEach((f) => {
                        const props = f.get('properties');
                        if (props) f.setProperties(props, true);
                    });
                    source.addFeatures(features);
                }
            } catch (error) {
                if ((error as Error).name !== 'AbortError') {
                    console.error('Error fetching health units:', error);
                }
            }
        })();

        return () => {
            controller.abort();
            map.removeLayer(layer);
            layerRef.current = null;
        };
    }, [map, api]);

    // Toggle visibility. Declared after the effect above so it also applies to a freshly created layer.
    useEffect(() => {
        layerRef.current?.setVisible(visible);
    }, [visible, map, api]);

    return null;
}
