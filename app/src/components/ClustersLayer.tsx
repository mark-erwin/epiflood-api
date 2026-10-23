import { useEffect, useMemo, useRef, useState } from 'react';
import type OLMap from 'ol/Map';
import Feature from 'ol/Feature';
import Point from 'ol/geom/Point';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import { fromLonLat } from 'ol/proj';
import { Circle as CircleStyle, Fill, Stroke, Style, Text } from 'ol/style';
import type { FeatureLike } from 'ol/Feature';
import RainfallChoroplethLayer, { RainfallLegend } from './RainfallChoroplethLayer';

/* ---------- types ---------- */

// Values must match the Disease enum on the API.
type Disease = 'dengue' | 'leptospirosis';

interface CaseWindow {
    start_date: string; // ISO date, e.g. "2026-08-23"
    end_date: string;
}

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
}

/* ---------- config ---------- */

const DISEASES: { value: Disease; label: string; fill: string; stroke: string }[] = [
    { value: 'dengue', label: 'Dengue', fill: 'rgba(220, 38, 38, 0.45)', stroke: 'rgba(153, 27, 27, 0.9)' },
    { value: 'leptospirosis', label: 'Leptospirosis', fill: 'rgba(217, 119, 6, 0.45)', stroke: 'rgba(146, 64, 14, 0.9)' },
];

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

/* ---------- helpers ---------- */

// Parse as local time so "2026-08-23" doesn't shift a day in some timezones.
function fmt(iso: string, withYear = false): string {
    return new Date(`${iso}T00:00:00`).toLocaleDateString('en-PH', {
        month: 'short',
        day: 'numeric',
        ...(withYear ? { year: 'numeric' } : {}),
    });
}

function windowLabel(w: CaseWindow): string {
    return `${fmt(w.start_date)} to ${fmt(w.end_date, true)}`;
}

/* ---------- component ---------- */

export default function ClustersLayer({ map, api }: Props) {
    const [disease, setDisease] = useState<Disease | null>(null);
    // Windows are stored with the disease they belong to so a stale list is never used.
    const [windowState, setWindowState] = useState<{ disease: Disease; items: CaseWindow[] } | null>(null);
    const [index, setIndex] = useState(0);
    const [summary, setSummary] = useState<{ barangays: number; cases: number } | null>(null);
    const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle');
    const [showRainfall, setShowRainfall] = useState(true);

    const sourceRef = useRef<VectorSource | null>(null);

    // Windows for the active disease, or an empty list while they load.
    const windows = useMemo(
        () => (windowState && windowState.disease === disease ? windowState.items : []),
        [windowState, disease],
    );
    const current = windows[index];

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

    // 2. Load the available windows when the disease changes.
    useEffect(() => {
        sourceRef.current?.clear();
        map.set('namedClusters', new Set<string>());
        setSummary(null);

        if (!disease) {
            setStatus('idle');
            return;
        }

        const controller = new AbortController();
        setStatus('loading');

        fetch(`${api}/map/clusters/${disease}/windows`, { signal: controller.signal })
            .then((res) => {
                if (!res.ok) throw new Error(`Windows request failed: ${res.status}`);
                return res.json() as Promise<CaseWindow[]>;
            })
            .then((items) => {
                // API returns newest first; the slider reads oldest to newest.
                const sorted = [...items].sort((a, b) => a.start_date.localeCompare(b.start_date));
                setWindowState({ disease, items: sorted });
                setIndex(Math.max(sorted.length - 1, 0)); // start on the latest window
                if (sorted.length === 0) setStatus('idle');
            })
            .catch((err) => {
                if (err.name !== 'AbortError') {
                    console.error(err);
                    setStatus('error');
                }
            });

        return () => controller.abort();
    }, [api, disease, map]);

    // 3. Load the circles for the selected window (debounced while dragging).
    useEffect(() => {
        if (!disease || !current) return;

        const controller = new AbortController();
        const timer = setTimeout(() => {
            setStatus('loading');
            const params = new URLSearchParams({ start: current.start_date, end: current.end_date });

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

                    setSummary({
                        barangays: rows.length,
                        cases: rows.reduce((sum, r) => sum + r.cases, 0),
                    });
                    setStatus('idle');
                })
                .catch((err) => {
                    if (err.name !== 'AbortError') {
                        console.error(err);
                        setStatus('error');
                    }
                });
        }, 150);

        return () => {
            clearTimeout(timer);
            controller.abort();
        };
    }, [api, disease, current, map]);

    function pickDisease(value: Disease) {
        // Clicking the active disease again hides the layer.
        setDisease((prev) => (prev === value ? null : value));
    }

    const rainfallOn = showRainfall && !!disease && !!current;

    return (
        <>
            <RainfallChoroplethLayer
                map={map}
                api={api}
                start={rainfallOn ? current.start_date : null}
                end={rainfallOn ? current.end_date : null}
            />

            <div style={styles.panel}>
                <div style={styles.title}>Show cases for</div>
                <div style={styles.buttons} role="group" aria-label="Disease">
                    {DISEASES.map((d) => (
                        <button
                            key={d.value}
                            type="button"
                            aria-pressed={disease === d.value}
                            onClick={() => pickDisease(d.value)}
                            style={{
                                ...styles.button,
                                ...(disease === d.value ? { ...styles.buttonActive, borderColor: d.stroke, background: d.fill } : {}),
                            }}
                        >
                            {d.label}
                        </button>
                    ))}
                </div>

                {disease && (
                    <label style={styles.toggle}>
                        <input
                            type="checkbox"
                            checked={showRainfall}
                            onChange={(e) => setShowRainfall(e.target.checked)}
                        />
                        Show rainfall (mm)
                    </label>
                )}

                {disease && windows.length > 0 && current && (
                    <div style={styles.sliderBlock}>
                        <div style={styles.windowLabel}>{windowLabel(current)}</div>
                        <input
                            type="range"
                            min={0}
                            max={windows.length - 1}
                            step={1}
                            value={index}
                            onChange={(e) => setIndex(Number(e.target.value))}
                            aria-label="Reporting period"
                            aria-valuetext={windowLabel(current)}
                            style={styles.slider}
                        />
                        <div style={styles.range}>
                            <span>{fmt(windows[0].start_date, true)}</span>
                            <span>{fmt(windows[windows.length - 1].end_date, true)}</span>
                        </div>
                    </div>
                )}

                {rainfallOn && <RainfallLegend />}

                <div style={styles.footer} aria-live="polite">
                    {status === 'loading' && 'Loading...'}
                    {status === 'error' && 'Could not load cases. Check the API and try again.'}
                    {status === 'idle' && disease && windows.length === 0 && 'No reporting periods found.'}
                    {status === 'idle' && summary && `${summary.barangays} barangays reporting, ${summary.cases} cases`}
                    {status === 'idle' && !disease && 'Choose a disease to see clusters.'}
                </div>
            </div>
        </>
    );
}

/* ---------- panel styles ---------- */

const styles: Record<string, React.CSSProperties> = {
    panel: {
        position: 'absolute',
        left: 16,
        bottom: 16,
        zIndex: 30,
        width: 280,
        maxWidth: 'calc(100% - 32px)',
        padding: 14,
        borderRadius: 10,
        background: 'rgba(255, 255, 255, 0.96)',
        boxShadow: '0 2px 10px rgba(0, 0, 0, 0.2)',
        font: '13px system-ui, sans-serif',
        color: '#1f2937',
    },
    title: { fontWeight: 600, marginBottom: 8 },
    buttons: { display: 'flex', gap: 8 },
    button: {
        flex: 1,
        padding: '7px 10px',
        borderRadius: 6,
        border: '1px solid #cbd5e1',
        background: '#fff',
        color: 'inherit',
        font: 'inherit',
        cursor: 'pointer',
    },
    buttonActive: { fontWeight: 600 },
    toggle: { display: 'flex', alignItems: 'center', gap: 6, marginTop: 10, cursor: 'pointer' },
    sliderBlock: { marginTop: 14 },
    windowLabel: { fontWeight: 600, marginBottom: 6 },
    slider: { width: '100%', cursor: 'pointer' },
    range: { display: 'flex', justifyContent: 'space-between', color: '#6b7280', fontSize: 11 },
    footer: { marginTop: 12, color: '#4b5563', minHeight: 16 },
};