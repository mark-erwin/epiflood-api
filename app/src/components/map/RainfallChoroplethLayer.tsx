import { useEffect, useRef } from 'react';
import type OLMap from 'ol/Map';
import type Feature from 'ol/Feature';
import type { FeatureLike } from 'ol/Feature';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import GeoJSON from 'ol/format/GeoJSON';
import { Fill, Style } from 'ol/style';

interface Props {
    map: OLMap;
    api: string;
    start: string | null; // YYYY-MM-DD, null hides the layer
    end: string | null;
    opacity?: number;
}

interface RainfallRow {
    barangay_pcode: string;
    precipitation_mm: number | null;
}

type RainfallLayer = VectorLayer<VectorSource<Feature>>;

// Same candidate pcode fields as the outlines layer.
const PCODE_PROPS = ['barangay_pcode', 'pcode', 'PCODE', 'adm4_pcode', 'ADM4_PCODE'];

// Upper bound (exclusive) of each bin, in mm. Adjust to your window length.
export const RAINFALL_BINS = [
    { max: 10, color: '#eff6ff', label: '< 10' },
    { max: 25, color: '#bfdbfe', label: '10 – 25' },
    { max: 50, color: '#60a5fa', label: '25 – 50' },
    { max: 100, color: '#2563eb', label: '50 – 100' },
    { max: 200, color: '#1e3a8a', label: '100 – 200' },
    { max: Infinity, color: '#4c1d95', label: '≥ 200' },
];

const binStyles = RAINFALL_BINS.map((b) => new Style({ fill: new Fill({ color: b.color }) }));
const noDataStyle = new Style({ fill: new Fill({ color: 'rgba(148, 163, 184, 0.15)' }) });

function styleForMm(mm: number): Style {
    const i = RAINFALL_BINS.findIndex((b) => mm < b.max);
    return binStyles[i === -1 ? binStyles.length - 1 : i];
}

function getPcode(feature: FeatureLike): string | null {
    for (const prop of PCODE_PROPS) {
        const v = feature.get(prop);
        if (v !== undefined && v !== null) return String(v);
    }
    return null;
}

export default function RainfallChoroplethLayer({ map, api, start, end, opacity = 0.65 }: Props) {
    const layerRef = useRef<RainfallLayer | null>(null);
    const dataRef = useRef<Map<string, number>>(new Map());

    // 1. Create the layer once per map/api.
    useEffect(() => {
        const layer: RainfallLayer = new VectorLayer({
            zIndex: 6, // above flood (5), below outlines (10) and circles (20)
            opacity,
            visible: false,
            source: new VectorSource<Feature>({
                url: `${api}/map/barangays`,
                format: new GeoJSON({ featureProjection: 'EPSG:3857' }),
            }),
            style: (feature) => {
                const pcode = getPcode(feature);
                const mm = pcode ? dataRef.current.get(pcode) : undefined;
                return mm === undefined ? noDataStyle : styleForMm(mm);
            },
        });

        layerRef.current = layer;
        map.addLayer(layer);
        return () => {
            map.removeLayer(layer);
            layer.dispose();
            layerRef.current = null;
        };
    }, [map, api]); // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        layerRef.current?.setOpacity(opacity);
    }, [opacity]);

    // 2. Follow the slider: refetch (debounced) whenever the window changes.
    useEffect(() => {
        const layer = layerRef.current;
        if (!layer) return;

        if (!start || !end) {
            dataRef.current = new Map();
            layer.setVisible(false);
            return;
        }

        layer.setVisible(true);
        const controller = new AbortController();
        const timer = setTimeout(async () => {
            try {
                const params = new URLSearchParams({ start, end });
                const res = await fetch(`${api}/map/rainfall?${params}`, {
                    signal: controller.signal,
                });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const rows: RainfallRow[] = await res.json();

                const next = new Map<string, number>();
                for (const r of rows) {
                    if (r.precipitation_mm !== null && r.precipitation_mm !== undefined) {
                        next.set(String(r.barangay_pcode), Number(r.precipitation_mm));
                    }
                }
                dataRef.current = next;
            } catch (err) {
                if ((err as Error).name === 'AbortError') return;
                console.error('Failed to load rainfall', err);
                dataRef.current = new Map();
            }
            layer.changed();
        }, 150);

        return () => {
            clearTimeout(timer);
            controller.abort();
        };
    }, [api, start, end]);

    return null;
}

export function RainfallLegend() {
    const swatch = (background: string): React.CSSProperties => ({
        width: 14,
        height: 10,
        background,
        border: '1px solid #cbd5e1',
        display: 'inline-block',
    });

    return (
        <div style={{ marginTop: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Rainfall (mm)</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 10px', fontSize: 11 }}>
                {RAINFALL_BINS.map((b) => (
                    <span key={b.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <span style={swatch(b.color)} />
                        {b.label}
                    </span>
                ))}
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <span style={swatch('rgba(148, 163, 184, 0.15)')} />
                    No data
                </span>
            </div>
        </div>
    );
}