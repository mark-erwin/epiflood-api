import { useEffect, useMemo, useState } from 'react';
import type OLMap from 'ol/Map';
import ClustersLayer from './ClustersLayer';
import HealthUnitsLayer from './HealthUnitsLayer';
import RainfallChoroplethLayer, { RainfallLegend } from './RainfallChoroplethLayer';
import { DISEASES } from './clusterConfig';
import type { CaseWindow, ClusterSummary, Disease, LoadStatus } from './clusterConfig';

interface Props {
    map: OLMap;
    api: string;
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

// Single control panel for the map: layer checkboxes, disease picker, period slider
// and legends. It also mounts the data layers it controls, so Map.tsx only needs
// <MapOptions map={map} api={api} />.
export default function MapOptions({ map, api }: Props) {
    const [open, setOpen] = useState(true);

    // Layer toggles.
    const [showHealthUnits, setShowHealthUnits] = useState(true);
    const [showRainfall, setShowRainfall] = useState(true);

    // Disease + reporting period.
    const [disease, setDisease] = useState<Disease | null>(null);
    // Windows are stored with the disease they belong to so a stale list is never used.
    const [windowState, setWindowState] = useState<{ disease: Disease; items: CaseWindow[] } | null>(null);
    const [windowsStatus, setWindowsStatus] = useState<LoadStatus>('idle');
    const [index, setIndex] = useState(0);

    // Reported back by ClustersLayer.
    const [clusterStatus, setClusterStatus] = useState<LoadStatus>('idle');
    const [summary, setSummary] = useState<ClusterSummary | null>(null);

    const windows = useMemo(
        () => (windowState && windowState.disease === disease ? windowState.items : []),
        [windowState, disease],
    );
    const windowsReady = windowState?.disease === disease;
    const current: CaseWindow | undefined = windows[index];

    // Load the available reporting windows when the disease changes.
    useEffect(() => {
        if (!disease) {
            setWindowsStatus('idle');
            return;
        }

        const controller = new AbortController();
        setWindowsStatus('loading');

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
                setWindowsStatus('idle');
            })
            .catch((err) => {
                if (err.name !== 'AbortError') {
                    console.error(err);
                    setWindowsStatus('error');
                }
            });

        return () => controller.abort();
    }, [api, disease]);

    function pickDisease(value: Disease) {
        // Clicking the active disease again hides the layer.
        setDisease((prev) => (prev === value ? null : value));
    }

    const rainfallOn = showRainfall && !!disease && !!current;

    // Status line at the bottom of the panel.
    let message = '';
    if (!disease) message = 'Choose a disease to see clusters.';
    else if (windowsStatus === 'error' || clusterStatus === 'error') message = 'Could not load cases. Check the API and try again.';
    else if (windowsStatus === 'loading' || clusterStatus === 'loading') message = 'Loading...';
    else if (windowsReady && windows.length === 0) message = 'No reporting periods found.';
    else if (summary) message = `${summary.barangays} barangays reporting, ${summary.cases} cases`;

    return (
        <>
            {/* Data layers controlled by this panel (they render nothing themselves). */}
            <HealthUnitsLayer map={map} api={api} visible={showHealthUnits} />
            <ClustersLayer
                map={map}
                api={api}
                disease={disease}
                period={current ?? null}
                onStatus={setClusterStatus}
                onSummary={setSummary}
            />
            <RainfallChoroplethLayer
                map={map}
                api={api}
                start={rainfallOn ? current.start_date : null}
                end={rainfallOn ? current.end_date : null}
            />

            <div style={styles.panel}>
                <div style={{ ...styles.header, marginBottom: open ? 10 : 0 }}>
                    <div style={styles.title}>Map options</div>
                    <button
                        type="button"
                        style={styles.collapse}
                        aria-expanded={open}
                        onClick={() => setOpen((o) => !o)}
                    >
                        {open ? 'Hide' : 'Show'}
                    </button>
                </div>

                {open && (
                    <>
 {/* Disease + period */}
                        <div style={{ ...styles.sectionTitle, marginTop: 14 }}>Show cases for</div>
                        <div style={styles.buttons} role="group" aria-label="Disease">
                            {DISEASES.map((d) => (
                                <button
                                    key={d.value}
                                    type="button"
                                    aria-pressed={disease === d.value}
                                    onClick={() => pickDisease(d.value)}
                                    style={{
                                        ...styles.button,
                                        ...(disease === d.value
                                            ? { ...styles.buttonActive, borderColor: d.stroke, background: d.fill }
                                            : {}),
                                    }}
                                >
                                    {d.label}
                                </button>
                            ))}
                        </div>

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

                        {/* Layers */}
                        <div style={styles.sectionTitle}>Layers</div>
                        <label style={styles.toggle}>
                            <input
                                type="checkbox"
                                checked={showHealthUnits}
                                onChange={(e) => setShowHealthUnits(e.target.checked)}
                            />
                            Health units
                        </label>
                        <label style={{ ...styles.toggle, ...(disease ? {} : styles.disabled) }}>
                            <input
                                type="checkbox"
                                checked={showRainfall}
                                disabled={!disease}
                                onChange={(e) => setShowRainfall(e.target.checked)}
                            />
                            Rainfall (mm)
                        </label>

                       

                        {/* Legends */}
                        {rainfallOn && (
                            <div style={styles.legendBlock}>
                                <RainfallLegend />
                            </div>
                        )}

                        <div style={styles.footer} aria-live="polite">
                            {message}
                        </div>
                    </>
                )}
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
        maxHeight: 'calc(100% - 32px)',
        overflowY: 'auto',
        padding: 14,
        borderRadius: 10,
        background: 'rgba(255, 255, 255, 0.96)',
        boxShadow: '0 2px 10px rgba(0, 0, 0, 0.2)',
        font: '13px system-ui, sans-serif',
        color: '#1f2937',
    },
    header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
    title: { fontWeight: 700, fontSize: 14 },
    collapse: {
        padding: '2px 8px',
        borderRadius: 6,
        border: '1px solid #cbd5e1',
        background: '#fff',
        color: 'inherit',
        font: 'inherit',
        fontSize: 12,
        cursor: 'pointer',
    },
    sectionTitle: { fontWeight: 600, marginBottom: 6 },
    toggle: { display: 'flex', alignItems: 'center', gap: 6, marginTop: 6, cursor: 'pointer' },
    disabled: { opacity: 0.5, cursor: 'not-allowed' },
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
    sliderBlock: { marginTop: 14 },
    windowLabel: { fontWeight: 600, marginBottom: 6 },
    slider: { width: '100%', cursor: 'pointer' },
    range: { display: 'flex', justifyContent: 'space-between', color: '#6b7280', fontSize: 11 },
    legendBlock: { marginTop: 14 },
    footer: { marginTop: 12, color: '#4b5563', minHeight: 16 },
};
