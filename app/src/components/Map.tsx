import { useEffect, useRef, useState } from 'react';
import 'ol/ol.css';
import OLMap from 'ol/Map';
import View from 'ol/View';
import TileLayer from 'ol/layer/Tile';
import VectorLayer from 'ol/layer/Vector';
import XYZ from 'ol/source/XYZ';
import VectorSource from 'ol/source/Vector';
import GeoJSON from 'ol/format/GeoJSON';
import { Fill, Icon, Stroke, Style, Text } from 'ol/style';
import type { FeatureLike } from 'ol/Feature';
import { fromLonLat, transformExtent } from 'ol/proj';
import { faHouseMedical } from '@fortawesome/free-solid-svg-icons';
import FloodLayer from './FloodLayer';

const MAX_CHARS = 18; // about 130px at 12px bold; raise for wider labels
const MAX_LINES = 3;  // anything longer is cut off with an ellipsis

const LABEL_MIN_ZOOM = 15; // labels appear at this zoom and closer
const LABEL_MAX_RESOLUTION = 156543.03392804097 / 2 ** LABEL_MIN_ZOOM;


function wrapLabel(text: string, maxChars = MAX_CHARS, maxLines = MAX_LINES): string {
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

function faToDataUri(def: typeof faHouseMedical, color: string, size = 32): string {
    const [w, h, , , path] = def.icon;
    const d = Array.isArray(path) ? path.join(' ') : path;
    const svg =
        `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${w} ${h}">` +
        `<path fill="${color}" d="${d}"/></svg>`;
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

const iconStyle = new Style({
    image: new Icon({
        src: faToDataUri(faHouseMedical, '#54228D', 32),
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
                text: wrapLabel(name),
                font: 'bold 12px "Montserrat", sans-serif',
                textAlign: 'center',
                offsetY: 32,
                fill: new Fill({ color: '#1f2937' }),
                stroke: new Stroke({ color: '#FBF8F3', width: 3 }),
            }),
        }),
    ]);
}

export default function Map() {
    const API_ADDRESS = import.meta.env.VITE_API_ADDRESS;

    const mapEl = useRef<HTMLDivElement>(null);
    const [map, setMap] = useState<OLMap | null>(null);

    // Create the map once
    useEffect(() => {
        if (!mapEl.current) return;

        // Leaflet: [[south, west], [north, east]] -> OL: [minLon, minLat, maxLon, maxLat]
        const lagunaExtent = transformExtent(
            [121.0053, 13.9635, 121.6346, 14.5958],
            'EPSG:4326',
            'EPSG:3857'
        );

        const unitsSource = new VectorSource();
        const unitsLayer = new VectorLayer({
            source: unitsSource,
            style: hospitalStyle,
            zIndex: 10,
        });

        document.fonts.load('600 12px "Montserrat"').then(() => {
            unitsLayer.changed();
        });

        const olMap = new OLMap({
            target: mapEl.current,
            layers: [
                new TileLayer({
                    source: new XYZ({
                        url: `https://{a-d}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${import.meta.env.VITE_CARTO_KEY}`,
                        maxZoom: 20,
                        attributions:
                            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, ' +
                            '&copy; <a href="https://carto.com/attributions">CARTO</a>',
                    }),
                }),
                unitsLayer,
            ],
            view: new View({
                center: fromLonLat([121.2431, 14.1797]),
                zoom: 13,
                minZoom: 12,
                maxZoom: 18,
                extent: lagunaExtent, // keeps the viewport inside Laguna, like maxBoundsViscosity: 1
            }),
        });

        // Fetch health units and load the GeoJSON straight into the vector source
        const controller = new AbortController();
        (async () => {
            try {
                const res = await fetch(`${API_ADDRESS}/health-units`, { signal: controller.signal });
                const data = await res.json();
                if (data?.features) {
                    const features = new GeoJSON().readFeatures(data, {
                        dataProjection: 'EPSG:4326',
                        featureProjection: 'EPSG:3857',
                    });
                    // Flatten properties.name so feature.get('name') works
                    features.forEach((f) => {
                        const props = f.get('properties');
                        if (props) f.setProperties(props, true);
                    });
                    unitsSource.addFeatures(features);
                }
            } catch (error) {
                if ((error as Error).name !== 'AbortError') {
                    console.error('Error fetching data:', error);
                }
            }
        })();

        setMap(olMap);

        return () => {
            controller.abort();
            olMap.setTarget(undefined);
            setMap(null);
        };
    }, [API_ADDRESS]);

    return (
        <div className="flex-1 w-max">
            <div ref={mapEl} style={{ height: '100vh', width: '100vw' }} />
            {map && <FloodLayer map={map} api={API_ADDRESS} />}
        </div>
    );
}
