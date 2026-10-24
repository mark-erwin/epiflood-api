import { useEffect, useRef } from 'react';
import type OLMap from 'ol/Map';
import Feature from 'ol/Feature';
import Point from 'ol/geom/Point';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import { fromLonLat } from 'ol/proj';
import { Circle as CircleStyle, Fill, Stroke, Style, Text } from 'ol/style';
import type { FeatureLike } from 'ol/Feature';
import { DISEASES } from './clusterConfig';
import type { CaseWindow, ClusterSummary, Disease, LoadStatus } from './clusterConfig';

/* ---------- types ---------- */

interface ClusterRow {
    barangay_pcode: string;
    barangay_name: string;
    municipality_name: string;
    longitude: number;
    latitude: number;
    cases: number;
    start_date: string;
    end_date: string;
}

interface Props {
    map: OLMap;
    api: string;
    /** Selected disease, or null to hide the layer. */
    disease: Disease | null;
    /** Selected reporting period, or null while windows are loading. */
    period: CaseWindow | null;
    /** Called with the load state of the circles. Pass a stable function (e.g. a useState setter). */
    onStatus: (status: LoadStatus) => void;
    /** Called with the totals for the visible circles, or null when nothing is shown. */
    onSummary: (summary: ClusterSummary | null) => void;
}

/* ---------- config ---------- */

// Radius in pixels, scaled against the largest barangay in the selected window:
//   radius = MIN_R + (cases / maxCases) ^ EXPONENT * (MAX_R - MIN_R)
// The biggest barangay always gets MAX_R, the smallest is close to MIN_R.
// EXPONENT: 0.5 = circle area proportional to cases, 1 = linear, higher = more drastic.
const MIN_R = 3;
const MAX_R = 60;
const EXPONENT = 1;

// Circles at least this big show the case count inside.
const LABEL_MIN_R = 12;
// Circles at least this big show the barangay name inside (above the count).
// Smaller circles show the name just below the circle instead.
const NAME_MIN_R = 28;

function radiusFor(ratio: number): number {
    return MIN_R + Math.pow(ratio, EXPONENT) * (MAX_R - MIN_R);
}

// Break a long name onto several lines, roughly as wide as the circle.
function wrapName(name: string, radius: number): string {
    const maxChars = Math.max(8, Math.floor(radius / 3.5));
    const lines: string[] = [];
    let line = '';
    for (const word of name.split(' ')) {
        if (line && (line + ' ' + word).length > maxChars) {
            lines.push(line);
            line = word;
        } else {
            line = line ? `${line} ${word}` : word;
        }
    }
    if (line) lines.push(line);
    return lines.join('\n');
}

// Same normalisation is used by the outline layer for name matching.
function normName(name: string): string {
    return name.trim().toLowerCase();
}

/* ---------- styling ---------- */

const styleCache = new Map<string, Style[]>();

function styleFor(feature: FeatureLike): Style[] {
    const cases = Number(feature.get('cases')) || 0;
    const ratio = Number(feature.get('ratio')) || 0; // cases / maxCases, set when features are built
    const disease = feature.get('disease') as Disease;
    const name = String(feature.get('name') ?? '');
    const key = `${disease}:${cases}:${Math.round(ratio * 1000)}:${name}`;

    let styles = styleCache.get(key);
    if (!styles) {
        const palette = DISEASES.find((d) => d.value === disease) ?? DISEASES[0];
        const radius = radiusFor(ratio);
        const insideStroke = new Stroke({ color: 'rgba(0,0,0,0.6)', width: 2 });

        // Text drawn inside the circle (white).
        let inside: string | undefined;
        if (radius >= NAME_MIN_R && name) inside = `${wrapName(name, radius)}\n${cases}`;
        else if (radius >= LABEL_MIN_R) inside = String(cases);

        const circle = new Style({
            image: new CircleStyle({
                radius,
                fill: new Fill({ color: palette.fill }),
                stroke: new Stroke({ color: palette.stroke, width: 0.5 }),
            }),
            text: inside
                ? new Text({
                    text: inside,
                    font: '12px system-ui, sans-serif',
                    fill: new Fill({ color: '#fff' }),
                    stroke: insideStroke,
                })
                : undefined,
        });
        styles = [circle];

        // Smaller circles: put the name just below the circle (dark text, white halo).
        if (radius < NAME_MIN_R && name) {
            const below = radius < LABEL_MIN_R ? `${name} (${cases})` : name;
            styles.push(
                new Style({
                    text: new Text({
                        text: below,
                        font: '11px system-ui, sans-serif',
                        offsetY: radius + 9,
                        fill: new Fill({ color: '#1f2937' }),
                        stroke: new Stroke({ color: 'rgba(255,255,255,0.95)', width: 3 }),
                    }),
                }),
            );
        }

        styleCache.set(key, styles);
    }
    return styles;
}

/* ---------- component ---------- */

// Draws the case circles on the map. All controls live in MapOptions.
export default function ClustersLayer({ map, api, disease, period, onStatus, onSummary }: Props) {
    const sourceRef = useRef<VectorSource | null>(null);

    // 1. Create the circle layer once per map.
    useEffect(() => {
        const source = new VectorSource();
        const layer = new VectorLayer({
            zIndex: 20,
            source,
            style: styleFor,
            // Draw small circles on top of big ones so they never get buried.
            renderOrder: (a, b) => Number(b.get('cases')) - Number(a.get('cases')),
        });
        sourceRef.current = source;
        map.addLayer(layer);

        return () => {
            map.set('namedClusters', new Set<string>());
            map.removeLayer(layer);
            layer.dispose();
            sourceRef.current = null;
        };
    }, [map]);

    // 2. Clear everything when the disease changes (or is switched off).
    useEffect(() => {
        sourceRef.current?.clear();
        map.set('namedClusters', new Set<string>());
        onSummary(null);
        onStatus('idle');
    }, [disease, map, onStatus, onSummary]);

    // 3. Load the circles for the selected window (debounced while dragging the slider).
    useEffect(() => {
        if (!disease || !period) return;

        const controller = new AbortController();
        const timer = setTimeout(() => {
            onStatus('loading');
            const params = new URLSearchParams({ start: period.start_date, end: period.end_date });

            fetch(`${api}/map/clusters/${disease}?${params}`, { signal: controller.signal })
                .then(async (res) => {
                    if (res.status === 404) return [] as ClusterRow[]; // no data for this window
                    if (!res.ok) throw new Error(`Clusters request failed: ${res.status}`);
                    return (await res.json()) as ClusterRow[];
                })
                .then((rows) => {
                    const source = sourceRef.current;
                    if (!source) return;

                    // Largest barangay in this window; every circle is sized relative to it.
                    const maxCases = Math.max(1, ...rows.map((r) => r.cases));

                    const features = rows.map((r) => {
                        const f = new Feature({
                            geometry: new Point(fromLonLat([r.longitude, r.latitude])),
                            name: r.barangay_name,
                            municipality: r.municipality_name,
                            cases: r.cases,
                            ratio: r.cases / maxCases,
                            disease,
                        });
                        f.setId(r.barangay_pcode);
                        return f;
                    });

                    source.clear(true);
                    source.addFeatures(features);

                    // Every barangay with a circle now labels itself, so the outline layer
                    // should skip its own label for these. Publish both pcodes and names
                    // (the outline layer matches on pcode first, then falls back to name).
                    const keys = new Set<string>();
                    rows.forEach((r) => {
                        keys.add(`pcode:${r.barangay_pcode}`);
                        keys.add(`name:${normName(r.barangay_name)}`);
                    });
                    map.set('namedClusters', keys);

                    onSummary({
                        barangays: rows.length,
                        cases: rows.reduce((sum, r) => sum + r.cases, 0),
                    });
                    onStatus('idle');
                })
                .catch((err) => {
                    if (err.name !== 'AbortError') {
                        console.error(err);
                        onStatus('error');
                    }
                });
        }, 150);

        return () => {
            clearTimeout(timer);
            controller.abort();
        };
    }, [api, disease, period, map, onStatus, onSummary]);

    return null;
}
