import { useMemo, useState } from 'react';

// Adjust if your VITE_API_ADDRESS already includes /api/v1
const BASE = (import.meta.env.VITE_API_ADDRESS ?? 'http://localhost:8000').replace(/\/$/, '');

type Param = {
  name: string;
  label: string;
  kind: 'text' | 'date' | 'number' | 'select';
  options?: string[];
  def?: string;
  placeholder?: string;
  inPath?: boolean;
  required?: boolean;
};

type Endpoint = {
  id: string;
  group: string;
  title: string;
  desc: string;
  path: string;
  exportPath: string;
  params: Param[];
  rowsKey?: string; // set when the response is { key: value } and should become rows
};

const DISEASES = ['dengue', 'leptospirosis'];
const disease: Param = { name: 'disease', label: 'Disease', kind: 'select', options: DISEASES, def: 'dengue' };
const start: Param = { name: 'start', label: 'Start date', kind: 'date' };
const end: Param = { name: 'end', label: 'End date', kind: 'date' };
const reqStart: Param = { ...start, required: true };
const reqEnd: Param = { ...end, required: true };
const pcode = (name: string, label: string): Param => ({ name, label, kind: 'text', placeholder: 'PCODE' });
const geo = (opts: string[]): Param => ({ name: 'geography', label: 'Geography', kind: 'select', options: opts, def: opts[0] });
const yearFrom: Param = { name: 'year_from', label: 'Year from', kind: 'number', placeholder: '2016' };
const yearTo: Param = { name: 'year_to', label: 'Year to', kind: 'number', placeholder: '2025' };

const ENDPOINTS: Endpoint[] = [
  { id: 'cases', group: 'Cases', title: 'Cluster Cases by Barangay', desc: 'Disease cluster records, filterable by place and date.',
    path: '/cases/{disease}', exportPath: '/cases/export/{disease}',
    params: [{ ...disease, inPath: true }, pcode('municipality_pcode', 'Municipality'), pcode('barangay_pcode', 'Barangay'), start, end] },
  { id: 'dengue-weekly', group: 'Cases', title: 'Dengue Weekly across Laguna', desc: 'Weekly dengue cases and deaths across Laguna.',
    path: '/cases/dengue/laguna/weekly', exportPath: '/cases/export/dengue/laguna/weekly', params: [start, end] },

  { id: 'rain-weekly', group: 'Rainfall', title: 'Weekly Rainfall by Municipality', desc: 'Raw weekly rainfall per municipality.',
    path: '/rainfall/weekly', exportPath: '/rainfall/export/weekly', params: [pcode('municipality_pcode', 'Municipality'), start, end] },
  { id: 'rain-laguna', group: 'Rainfall', title: 'Weekly Rainfall across Laguna', desc: 'Raw weekly rainfall for the whole province.',
    path: '/rainfall/weekly/laguna', exportPath: '/rainfall/export/weekly/laguna', params: [start, end] },

  { id: 'disease-over-time', group: 'Analysis', title: 'Disease over Time', desc: 'Observed cluster records over time.',
    path: '/analysis/disease-over-time', exportPath: '/analysis/export/disease-over-time',
    params: [disease, pcode('pcode', 'Place code'), geo(['municipality', 'barangay']), start, end] },
  { id: 'rainfall-over-time', group: 'Analysis', title: 'Rainfall over Time', desc: 'Observed weekly rainfall, by municipality or Laguna.',
    path: '/analysis/rainfall-over-time', exportPath: '/analysis/export/rainfall-over-time',
    params: [geo(['municipality', 'laguna']), pcode('municipality_pcode', 'Municipality'), start, end] },
  { id: 'seasonality', group: 'Analysis', title: 'Seasonality', desc: 'Cluster cases summarized by ISO week of start date.',
    path: '/analysis/seasonality', exportPath: '/analysis/export/seasonality',
    params: [disease, pcode('pcode', 'Place code'), geo(['municipality', 'barangay']), yearFrom, yearTo] },
  { id: 'hazard', group: 'Analysis', title: 'Hazard Exposure', desc: 'Flood-hazard area compared with observed cases.',
    path: '/analysis/hazard-exposure', exportPath: '/analysis/export/hazard-exposure',
    params: [disease, { name: 'hazard_level', label: 'Hazard level', kind: 'select', options: ['1', '2', '3'], def: '2' },
      { name: 'year', label: 'Year', kind: 'number', placeholder: '2024' }, geo(['municipality', 'barangay'])] },

  { id: 'map-barangays', group: 'Map', title: 'Barangay Boundaries', desc: 'Barangay boundaries as GeoJSON. The table shows feature properties; JSON export gives full geometry.',
    path: '/map/barangays', exportPath: '/map/export/barangays', params: [] },
  { id: 'map-pcode', group: 'Map', title: 'Pcode Lookup', desc: 'Maps place codes to names.',
    path: '/map/pcode-lookup', exportPath: '/map/export/pcode-lookup', rowsKey: 'pcode', params: [] },
  { id: 'map-health', group: 'Map', title: 'Health Units', desc: 'Health facilities as GeoJSON points.',
    path: '/map/health-units', exportPath: '/map/export/health-units', params: [] },

  { id: 'municipalities', group: 'Reference', title: 'Municipalities', desc: 'All Laguna cities and municipalities.',
    path: '/municipalities', exportPath: '/municipalities/export',
    params: [{ name: 'search', label: 'Name contains', kind: 'text' }] },
  { id: 'barangays', group: 'Reference', title: 'Barangays', desc: 'Laguna barangays, by municipality then name.',
    path: '/barangays', exportPath: '/barangays/export',
    params: [{ name: 'search', label: 'Name contains', kind: 'text' }, pcode('municipality', 'Municipality')] },

  { id: 'sources', group: 'Meta', title: 'Data Sources', desc: 'Where each dataset came from, with coverage and row count.',
    path: '/sources', exportPath: '/sources/export', params: [] },
  { id: 'schema', group: 'Meta', title: 'Schema', desc: 'Every table and view with a short description.',
    path: '/schema', exportPath: '/schema/export', params: [] },
];

const GROUPS = ['Cases', 'Rainfall', 'Analysis', 'Map', 'Reference', 'Meta'];
const FORMATS = ['csv', 'json'];

type Row = Record<string, unknown>;
type Run =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ok'; rows: Row[]; raw: unknown; ms: number };

const defaults = (ep: Endpoint) => Object.fromEntries(ep.params.map((p) => [p.name, p.def ?? '']));

function buildUrl(ep: Endpoint, values: Record<string, string>, exporting = false, fmt = 'csv') {
  let path = exporting ? ep.exportPath : ep.path;
  const qs = new URLSearchParams();
  for (const p of ep.params) {
    const v = values[p.name];
    if (p.inPath) path = path.replace(`{${p.name}}`, encodeURIComponent(v || p.def || ''));
    else if (v) qs.set(p.name, v);
  }
  if (exporting) qs.set('fmt', fmt);
  const q = qs.toString();
  return `${BASE}${path}${q ? `?${q}` : ''}`;
}

const toRows = (data: unknown, keyName?: string): Row[] => {
  if (Array.isArray(data)) return data.map((d) => (d && typeof d === 'object' ? (d as Row) : { value: d }));
  if (data && typeof data === 'object') {
    const o = data as Row;
    // GeoJSON FeatureCollection: one row per feature, using its properties
    if (Array.isArray(o.features)) return o.features.map((f) => ({ ...(((f as Row).properties as Row) ?? {}) }));
    // { key: value | {…} | […] }: flatten like the backend's mapping_to_rows
    if (keyName) {
      return Object.entries(o).flatMap(([k, v]) => {
        if (Array.isArray(v)) return v.map((x) => ({ [keyName]: k, ...(x && typeof x === 'object' ? (x as Row) : { value: x }) }));
        if (v && typeof v === 'object') return [{ [keyName]: k, ...(v as Row) }];
        return [{ [keyName]: k, value: v }];
      });
    }
    return [o];
  }
  return [];
};

const fmtVal = (v: unknown) =>
  v === null || v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v);

const inputCls =
  'w-full rounded-lg border border-[#e1e6f0] bg-white px-3 py-2 text-sm text-[#1d2648] outline-none transition placeholder:text-[#9aa5c4] focus:border-[#3449a3] focus:ring-2 focus:ring-[#3449a3]/15';

export default function ExploreData() {
  const [epId, setEpId] = useState(ENDPOINTS[0].id);
  const ep = ENDPOINTS.find((e) => e.id === epId)!;
  const [values, setValues] = useState<Record<string, string>>(defaults(ep));
  const [fmt, setFmt] = useState('csv');
  const [run, setRun] = useState<Run>({ status: 'idle' });
  const [tab, setTab] = useState<'table' | 'json'>('table');
  const [copied, setCopied] = useState(false);

  const url = buildUrl(ep, values);
  const exportUrl = buildUrl(ep, values, true, fmt);
  const missing = ep.params.filter((p) => p.required && !values[p.name]);

  const select = (id: string) => {
    const next = ENDPOINTS.find((e) => e.id === id)!;
    setEpId(id);
    setValues(defaults(next));
    setRun({ status: 'idle' });
  };

  const send = async () => {
    setRun({ status: 'loading' });
    const t0 = performance.now();
    try {
      const res = await fetch(url);
      if (!res.ok) {
        let detail = `${res.status} ${res.statusText}`;
        try {
          const body = await res.json();
          if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
        } catch { /* keep default */ }
        throw new Error(detail);
      }
      const raw = await res.json();
      setRun({ status: 'ok', rows: toRows(raw, ep.rowsKey), raw, ms: Math.round(performance.now() - t0) });
    } catch (e) {
      setRun({ status: 'error', message: e instanceof Error ? e.message : 'Request failed' });
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard unavailable */ }
  };

  const columns = useMemo(() => (run.status === 'ok' && run.rows.length ? Object.keys(run.rows[0]) : []), [run]);

  return (
    <div className="flex min-h-full flex-col bg-[#f4f6fb] font-['Montserrat',sans-serif] text-[#1d2648] md:flex-row">
      {/* Endpoint list */}
      <aside className="shrink-0 border-b border-[#e1e6f0] bg-white p-5 md:w-72 md:border-b-0 md:border-r md:overflow-y-auto">
        {GROUPS.map((g) => (
          <div key={g} className="mb-5">
            <h2 className="mb-1.5 px-2 text-xs font-semibold text-[#8390b5]">{g}</h2>
            <ul className="space-y-0.5">
              {ENDPOINTS.filter((e) => e.group === g).map((e) => (
                <li key={e.id}>
                  <button
                    onClick={() => select(e.id)}
                    className={`w-full rounded-lg px-2 py-1.5 text-left text-sm transition ${
                      e.id === epId ? 'bg-[#eef1ff] font-semibold text-[#3449a3]' : 'text-[#33406b] hover:bg-[#f4f6fb]'
                    }`}
                  >
                    {e.title}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </aside>

      {/* Workspace */}
      <main className="min-w-0 flex-1 space-y-5 p-5 md:overflow-y-auto md:p-8">
        <header>
          <h2 className="text-2xl font-bold tracking-tight text-[#080f43]">{ep.title}</h2>
          <p className="mt-1 text-sm text-[#5d6a91]">{ep.desc}</p>
        </header>

        {/* Parameters */}
        {ep.params.length > 0 && (
          <section className="rounded-2xl border border-[#e1e6f0] bg-white p-5 shadow-[0_8px_30px_rgba(8,15,67,0.05)]">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {ep.params.map((p) => (
                <label key={p.name} className="block">
                  <span className="mb-1 block text-xs font-medium text-[#5d6a91]">
                    {p.label}{p.required && <span className="text-[#b3261e]"> *</span>}
                  </span>
                  {p.kind === 'select' ? (
                    <select className={inputCls} value={values[p.name]} onChange={(e) => setValues({ ...values, [p.name]: e.target.value })}>
                      {!p.def && <option value="">Any</option>}
                      {p.options!.map((o) => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input
                      className={inputCls}
                      type={p.kind}
                      placeholder={p.placeholder}
                      value={values[p.name]}
                      onChange={(e) => setValues({ ...values, [p.name]: e.target.value })}
                    />
                  )}
                </label>
              ))}
            </div>
          </section>
        )}

        {/* URL + actions */}
        <section className="rounded-2xl bg-[#080f43] p-4 text-white">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 rounded-md bg-[#3449a3] px-2 py-0.5 text-xs font-semibold">GET</span>
            <code className="min-w-0 flex-1 break-all font-mono text-[13px] leading-relaxed text-[#cfd8ff]">{url}</code>
            <button onClick={copy} className="shrink-0 rounded-md px-2 py-1 text-xs text-[#cfd8ff] transition hover:bg-white/10">
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              onClick={send}
              disabled={run.status === 'loading' || missing.length > 0}
              title={missing.length ? `Required: ${missing.map((m) => m.label).join(', ')}` : undefined}
              className="rounded-lg bg-white px-5 py-2 text-sm font-semibold text-[#080f43] transition hover:bg-[#eef1ff] disabled:opacity-60"
            >
              {run.status === 'loading' ? 'Running…' : 'Run request'}
            </button>
            <div className="ml-auto flex items-center gap-2">
              <select
                aria-label="Export format"
                value={fmt}
                onChange={(e) => setFmt(e.target.value)}
                className="rounded-lg border border-white/20 bg-transparent px-2 py-2 text-sm text-white outline-none focus:border-white/60"
              >
                {FORMATS.map((f) => <option key={f} value={f} className="text-[#080f43]">{f.toUpperCase()}</option>)}
              </select>
              <a
                href={missing.length ? undefined : exportUrl}
                aria-disabled={missing.length > 0}
                download
                className={`rounded-lg border border-white/20 px-4 py-2 text-sm font-medium transition hover:bg-white/10 ${missing.length ? 'pointer-events-none opacity-50' : ''}`}
              >
                Export
              </a>
            </div>
          </div>
        </section>

        {/* Result */}
        <section className="rounded-2xl border border-[#e1e6f0] bg-white shadow-[0_8px_30px_rgba(8,15,67,0.05)]">
          {run.status === 'idle' && (
            <p className="p-10 text-center text-sm text-[#8390b5]">
              {missing.length ? `Fill in ${missing.map((m) => m.label.toLowerCase()).join(', ')} to run this request.` : 'Run the request to see data here.'}
            </p>
          )}
          {run.status === 'loading' && <p className="p-10 text-center text-sm text-[#5d6a91]">Loading…</p>}
          {run.status === 'error' && (
            <div className="p-6">
              <p className="text-sm font-semibold text-[#b3261e]">Request failed</p>
              <p className="mt-1 text-sm text-[#5d6a91]">{run.message}</p>
              <p className="mt-3 text-xs text-[#8390b5]">Check the parameters, and that the API is running at {BASE}.</p>
            </div>
          )}
          {run.status === 'ok' && (
            <>
              <div className="flex flex-wrap items-center gap-2 border-b border-[#e1e6f0] px-4 py-3">
                {(['table', 'json'] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={`rounded-lg px-3 py-1.5 text-sm capitalize transition ${
                      tab === t ? 'bg-[#eef1ff] font-semibold text-[#3449a3]' : 'text-[#5d6a91] hover:bg-[#f4f6fb]'
                    }`}
                  >
                    {t === 'json' ? 'JSON' : t}
                  </button>
                ))}
                <span className="ml-auto text-xs text-[#8390b5]">
                  {run.rows.length} {run.rows.length === 1 ? 'row' : 'rows'} · {run.ms} ms
                </span>
              </div>

              {run.rows.length === 0 && <p className="p-10 text-center text-sm text-[#8390b5]">No rows matched these parameters.</p>}

              {run.rows.length > 0 && tab === 'table' && (
                <div className="max-h-[28rem] overflow-auto">
                  <table className="w-full border-collapse text-left text-sm">
                    <thead className="sticky top-0 bg-[#f7f8fc] text-xs text-[#5d6a91]">
                      <tr>{columns.map((c) => <th key={c} className="whitespace-nowrap px-4 py-2.5 font-semibold">{c}</th>)}</tr>
                    </thead>
                    <tbody>
                      {run.rows.slice(0, 200).map((r, i) => (
                        <tr key={i} className="border-t border-[#eef1f8] hover:bg-[#f7f8fc]">
                          {columns.map((c) => <td key={c} className="whitespace-nowrap px-4 py-2">{fmtVal(r[c])}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {run.rows.length > 200 && (
                    <p className="border-t border-[#eef1f8] p-3 text-center text-xs text-[#8390b5]">
                      Showing the first 200 of {run.rows.length} rows. Export to get them all.
                    </p>
                  )}
                </div>
              )}

              {tab === 'json' && (
                <pre className="max-h-[28rem] overflow-auto p-4 font-mono text-xs leading-relaxed text-[#33406b]">
                  {JSON.stringify(run.raw, null, 2).slice(0, 50000)}
                </pre>
              )}
            </>
          )}
        </section>
      </main>
    </div>
  );
}