// Shared types and config for the disease cluster layer and the MapOptions panel.

// Values must match the Disease enum on the API.
export type Disease = 'dengue' | 'leptospirosis';

export interface CaseWindow {
    start_date: string; // ISO date, e.g. "2026-08-23"
    end_date: string;
}

export type LoadStatus = 'idle' | 'loading' | 'error';

export interface ClusterSummary {
    barangays: number;
    cases: number;
}

export const DISEASES: { value: Disease; label: string; fill: string; stroke: string }[] = [
    { value: 'dengue', label: 'Dengue', fill: 'rgba(220, 38, 38, 0.45)', stroke: 'rgba(153, 27, 27, 0.9)' },
    { value: 'leptospirosis', label: 'Leptospirosis', fill: 'rgba(217, 119, 6, 0.45)', stroke: 'rgba(146, 64, 14, 0.9)' },
];
