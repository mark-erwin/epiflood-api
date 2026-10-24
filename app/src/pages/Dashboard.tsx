
import { useEffect, useMemo, useState } from 'react';
import type { MouseEvent, ReactNode } from 'react';
import { Link } from 'react-router';

const BASE = (import.meta.env.VITE_API_ADDRESS ?? 'http://localhost:8000').replace(/\/$/, '');

type Row = Record<string, unknown>;
type Disease = 'dengue' | 'leptospirosis';
type ApiState = { status: 'loading' | 'ok' | 'error'; rows: Row[]; error?: string };
type Point = { x: string; y: number };
type DisplayColumn = { key: string; label: string; get: (r: Row) => string };

const DISEASES: { value: Disease; label: string }[] = [
  { value: 'dengue', label: 'Dengue' },
  { value: 'leptospirosis', label: 'Leptospirosis' },
];

const PERIODS = [
  { value: 'all', label: 'All time', years: 0 },
  { value: '5y', label: 'Last 5 years', years: 5 },
  { value: '3y', label: 'Last 3 years', years: 3 },
  { value: '1y', label: 'Last year', years: 1 },
];

const BLUE = '#3449a3';
const HIDDEN_COL = /start|(^|_)end(_|$)|end_?date|(^|_)(lat|lon|lng)(_|$)|latitude|longitude/i;
const SKIP = /pcode|id$|year|week|level|lat|lon|code/i;

/* ----------------------------------- data helpers ----------------------------------- */

const toRows = (data: unknown): Row[] => {
  if (Array.isArray(data)) {
    return data.map((d) =>
      d && typeof d === 'object' ? (d as Row) : { value: d },
    );
  }

  if (data && typeof data === 'object') {
    const inner = Object.values(data as Row).find(
      (v) => Array.isArray(v) && v.length > 0 && typeof v[0] === 'object',
    );
    return inner ? toRows(inner) : [data as Row];
  }

  return [];
};

const mappingToRows = (keyName: string) => (data: unknown): Row[] => {
  if (Array.isArray(data)) return toRows(data);
  if (!data || typeof data !== 'object') return [];

  return Object.entries(data as Row).flatMap(([k, v]) => {
    if (Array.isArray(v)) {
      return v.map((x) => ({
        [keyName]: k,
        ...(x && typeof x === 'object' ? (x as Row) : { value: x }),
      }));
    }

    if (v && typeof v === 'object') {
      return [{ [keyName]: k, ...(v as Row) }];
    }

    return [{ [keyName]: k, value: v }];
  });
};

const rainfallRows = mappingToRows('barangay_pcode');
const pcodeRows = mappingToRows('pcode');

const keysOf = (rows: Row[]) => (rows.length ? Object.keys(rows[0]) : []);

const isNumKey = (rows: Row[], k: string) =>
  rows.some((r) => typeof r[k] === 'number') &&
  rows.every((r) => r[k] == null || typeof r[k] === 'number');

const numKeys = (rows: Row[]) => keysOf(rows).filter((k) => isNumKey(rows, k));
const textKeys = (rows: Row[]) => keysOf(rows).filter((k) => !isNumKey(rows, k));

const metricKey = (
  rows: Row[],
  re: RegExp,
  opts: { not?: RegExp; skip?: string[] } = {},
) => {
  const nk = numKeys(rows).filter(
    (k) => !opts.not?.test(k) && !opts.skip?.includes(k),
  );

  return nk.find((k) => re.test(k)) ?? nk.find((k) => !SKIP.test(k));
};

const timeKey = (rows: Row[]) => {
  const ks = keysOf(rows);
  return (
    ks.find((k) => /date|start|month/i.test(k) && !isNumKey(rows, k)) ??
    ks.find((k) => /week/i.test(k)) ??
    ks.find((k) => /year/i.test(k)) ??
    ks[0] ??
    ''
  );
};

const labelKey = (rows: Row[]) => {
  const tk = textKeys(rows);
  return (
    tk.find((k) => /name|municipality|barangay|city/i.test(k)) ??
    tk.find((k) => !/code/i.test(k)) ??
    tk[0] ??
    keysOf(rows)[0] ??
    ''
  );
};

const sum = (rows: Row[], k?: string) =>
  k
    ? rows.reduce(
        (a, r) => a + (typeof r[k] === 'number' ? (r[k] as number) : 0),
        0,
      )
    : 0;

const distinct = (rows: Row[], k?: string) =>
  k ? new Set(rows.map((r) => r[k]).filter((v) => v != null)).size : 0;

const aggregate = (rows: Row[], xk: string, vk?: string): Point[] => {
  const m = new Map<string, number>();

  for (const r of rows) {
    if (r[xk] == null) continue;

    const add = vk
      ? typeof r[vk] === 'number'
        ? (r[vk] as number)
        : 0
      : 1;

    m.set(String(r[xk]), (m.get(String(r[xk])) ?? 0) + add);
  }

  const out = [...m.entries()].map(([x, y]) => ({ x, y }));
  const numeric = out.every(
    (p) => p.x.trim() !== '' && !Number.isNaN(Number(p.x)),
  );

  return out.sort((a, b) =>
    numeric ? Number(a.x) - Number(b.x) : a.x.localeCompare(b.x),
  );
};

const nf = new Intl.NumberFormat('en');
const compact = new Intl.NumberFormat('en', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

const num = (v: number) => nf.format(Math.round(v * 100) / 100);

const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?$/;

const formatDate = (s: string) => {
  const m = DATE_RE.exec(s);
  if (!m) return s;

  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));

  return d.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
};

const cell = (v: unknown) =>
  v === null || v === undefined
    ? ''
    : typeof v === 'object'
      ? JSON.stringify(v)
      : typeof v === 'number'
        ? num(v)
        : formatDate(String(v));

const pretty = (k: string) =>
  k.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());

/**
 * Builds a code -> name lookup.
 * Supports barangay and municipality data with common pcode/name column names.
 */
const buildNames = (
  rows: Row[],
  type: 'barangay' | 'municipality',
) => {
  const result = new Map<string, string>();

  for (const row of rows) {
    const entries = Object.entries(row);

    const codeKeys =
      type === 'barangay'
        ? [
            'barangay_pcode',
            'barangayPcode',
            'barangay_code',
            'barangayCode',
            'pcode',
            'code',
          ]
        : [
            'municipality_pcode',
            'municipalityPcode',
            'municipality_code',
            'municipalityCode',
            'muni_pcode',
            'pcode',
            'code',
          ];

    const nameKeys =
      type === 'barangay'
        ? [
            'barangay_name',
            'barangayName',
            'barangay',
            'name',
            'value',
          ]
        : [
            'municipality_name',
            'municipalityName',
            'municipality',
            'city_name',
            'city',
            'name',
            'value',
          ];

    const findKey = (candidates: string[]) =>
      candidates.find((candidate) =>
        entries.some(([key]) => key.toLowerCase() === candidate.toLowerCase()),
      );

    const codeKey = findKey(codeKeys);
    const nameKey = findKey(nameKeys);

    if (!codeKey || !nameKey) continue;

    const code = row[codeKey];
    const name = row[nameKey];

    if (
      code !== null &&
      code !== undefined &&
      name !== null &&
      name !== undefined &&
      String(name).trim() !== ''
    ) {
      result.set(String(code), String(name));
    }
  }

  return result;
};

/**
 * Replaces pcode columns with readable names while retaining other
 * useful fields, such as dates and case counts.
 */
const makeDisplayColumns = (
  rows: Row[],
  nameOf: (
    code: unknown,
    type?: 'barangay' | 'municipality',
  ) => string,
  limit = 8,
): DisplayColumn[] => {
  const ks = keysOf(rows);
  const columns: DisplayColumn[] = [];

  const municipalityCode = ks.find((k) =>
    /municipality.*(pcode|code)|(?:pcode|code).*municipality|muni_pcode/i.test(k),
  );

  const barangayCode = ks.find((k) =>
    /barangay.*(pcode|code)|(?:pcode|code).*barangay/i.test(k),
  );

  const municipalityName = ks.find((k) =>
    /^municipality$|^municipality_name$|^municipalityname$|^city_name$/i.test(k),
  );

  const barangayName = ks.find((k) =>
    /^barangay$|^barangay_name$|^barangayname$/i.test(k),
  );

  if (municipalityName) {
    columns.push({
      key: municipalityName,
      label: 'Municipality',
      get: (r) => cell(r[municipalityName]),
    });
  } else if (municipalityCode) {
    columns.push({
      key: '__municipality_name',
      label: 'Municipality',
      get: (r) => nameOf(r[municipalityCode], 'municipality'),
    });
  }

  if (barangayName) {
    columns.push({
      key: barangayName,
      label: 'Barangay',
      get: (r) => cell(r[barangayName]),
    });
  } else if (barangayCode) {
    columns.push({
      key: '__barangay_name',
      label: 'Barangay',
      get: (r) => nameOf(r[barangayCode], 'barangay'),
    });
  }

  for (const k of ks) {
    // Hide administrative codes because readable names replace them.
    if (/pcode|(^|_)(id|code)$/i.test(k)) continue;

    // Avoid duplicate municipality/barangay columns.
    if (k === municipalityName || k === barangayName) continue;

    if (HIDDEN_COL.test(k)) continue;

    columns.push({
      key: k,
      label: pretty(k),
      get: (r) => cell(r[k]),
    });
  }

  // Keep the generated name columns even if the table is otherwise narrow.
  const nameColumns = columns.filter(
    (c) => c.key === '__municipality_name' || c.key === '__barangay_name',
  );
  const otherColumns = columns.filter(
    (c) => c.key !== '__municipality_name' && c.key !== '__barangay_name',
  );

  return [...nameColumns, ...otherColumns].slice(0, Math.max(limit, nameColumns.length));
};
/* ------------------------------------- API hook ------------------------------------- */

function useApi(
  path: string | null,
  params: Record<string, string | undefined>,
  transform: (d: unknown) => Row[] = toRows,
): ApiState & { retry: () => void } {
  const qs = new URLSearchParams();

  for (const [k, v] of Object.entries(params)) {
    if (v) qs.set(k, v);
  }

  const url = path
    ? `${BASE}${path}${qs.toString() ? `?${qs}` : ''}`
    : null;

  const [state, setState] = useState<ApiState>({
    status: 'loading',
    rows: [],
  });

  const [tries, setTries] = useState(0);

  useEffect(() => {
    if (!url) {
      setState({ status: 'loading', rows: [] });
      return;
    }

    const ctl = new AbortController();

    setState((s) => ({ ...s, status: 'loading' }));

    fetch(url, { signal: ctl.signal })
      .then(async (res) => {
        if (!res.ok) {
          let msg = `${res.status} ${res.statusText}`;

          try {
            const b = await res.json();
            if (b?.detail) {
              msg =
                typeof b.detail === 'string'
                  ? b.detail
                  : JSON.stringify(b.detail);
            }
          } catch {
            // Keep the default error message.
          }

          throw new Error(msg);
        }

        return res.json();
      })
      .then((data) => {
        setState({ status: 'ok', rows: transform(data) });
      })
      .catch((e) => {
        if (e?.name !== 'AbortError') {
          setState({
            status: 'error',
            rows: [],
            error: e instanceof Error ? e.message : 'Request failed',
          });
        }
      });

    return () => ctl.abort();
  }, [url, tries, transform]);

  return { ...state, retry: () => setTries((n) => n + 1) };
}

/* ------------------------------------- dashboard ------------------------------------- */

export default function Dashboard() {
  const [disease, setDisease] = useState<Disease>('dengue');
  const [period, setPeriod] = useState('all');
  const [weeklyMetric, setWeeklyMetric] = useState<'cases' | 'deaths'>('cases');
  const [winIdx, setWinIdx] = useState<number | null>(null);

  const dName = DISEASES.find((d) => d.value === disease)!.label;
  const periodDef = PERIODS.find((p) => p.value === period)!;
  const periodText = periodDef.label.toLowerCase();

  const start = useMemo(() => {
    if (!periodDef.years) return undefined;

    const d = new Date();
    d.setFullYear(d.getFullYear() - periodDef.years);

    return d.toISOString().slice(0, 10);
  }, [periodDef.years]);

  const changeDisease = (d: Disease) => {
    setDisease(d);
    setWinIdx(null);
  };

  const clusters = useApi(`/cases/${disease}`, { start });

  const overTime = useApi('/analysis/disease-over-time', {
    disease,
    geography: 'municipality',
    start,
  });

  const season = useApi('/analysis/seasonality', {
    disease,
    year_from: start?.slice(0, 4),
  });

  const hazard = useApi('/analysis/hazard-exposure', {
    disease,
    hazard_level: '2',
    geography: 'municipality',
  });

  const weekly = useApi('/cases/dengue/laguna/weekly', { start });
  const rain = useApi('/rainfall/weekly/laguna', { start });

  const windowsApi = useApi(`/map/clusters/${disease}/windows`, {});

  const wsK = keysOf(windowsApi.rows).find((k) => /start/i.test(k));
  const weK = keysOf(windowsApi.rows).find((k) => /end/i.test(k));

  const windows = useMemo(
    () =>
      wsK && weK
        ? windowsApi.rows
            .map((r) => ({
              start: String(r[wsK]).slice(0, 10),
              end: String(r[weK]).slice(0, 10),
            }))
            .sort((a, b) => a.end.localeCompare(b.end))
        : [],
    [windowsApi.rows, wsK, weK],
  );

  const winPos = windows.length
    ? winIdx === null
      ? windows.length - 1
      : Math.min(winIdx, windows.length - 1)
    : 0;

  const win = windows[winPos];

  const mClusters = useApi(
    win ? `/map/clusters/${disease}` : null,
    { start: win?.start, end: win?.end },
  );

  const mRain = useApi(
    win ? '/map/rainfall' : null,
    { start: win?.start, end: win?.end },
    rainfallRows,
  );
const lookup = useApi('/map/pcode-lookup', {}, pcodeRows);
const brgys = useApi('/barangays', {});

const barangayNames = useMemo(
  () =>
    new Map([
      ...buildNames(lookup.rows, 'barangay'),
      ...buildNames(brgys.rows, 'barangay'),
    ]),
  [lookup.rows, brgys.rows],
);

const municipalityNames = useMemo(
  () => buildNames(lookup.rows, 'municipality'),
  [lookup.rows],
);

const nameOf = (
  code: unknown,
  type: 'barangay' | 'municipality' = 'barangay',
) => {
  const names =
    type === 'municipality' ? municipalityNames : barangayNames;

  return names.get(String(code)) ?? String(code ?? '');
};

  const mrKey = metricKey(mRain.rows, /total|sum|rain|precip|mm/i);

const clusterBarangayKey = keysOf(mClusters.rows).find(
  (k) => /barangay.*pcode|pcode.*barangay/i.test(k),
);

const rainfallBarangayKey = keysOf(mRain.rows).find(
  (k) => /barangay.*pcode|pcode.*barangay/i.test(k),
);



  /* Map-window cluster table */
  const mcCases = numKeys(mClusters.rows).find((k) => /case/i.test(k));

  const mcSorted = useMemo(
    () =>
      (mcCases
        ? [...mClusters.rows].sort(
            (a, b) => Number(b[mcCases]) - Number(a[mcCases]),
          )
        : mClusters.rows
      ).slice(0, 10),
    [mClusters.rows, mcCases],
  );

const mcColumns = useMemo(
  () => makeDisplayColumns(mcSorted, nameOf, 8),
  [mcSorted, barangayNames, municipalityNames],
);

const caseKey = metricKey(mClusters.rows, /cases|case_count|total_cases|count/i);

const mrBars = useMemo(() => {
  if (
    !mrKey ||
    !caseKey ||
    !clusterBarangayKey ||
    !rainfallBarangayKey
  ) {
    return [];
  }

  const casesByBarangay = new Map<string, number>();

  for (const row of mcSorted) {
    const code = row[clusterBarangayKey];
    const cases = row[caseKey];

    if (code == null || typeof cases !== "number") continue;

    const key = String(code);
    casesByBarangay.set(
      key,
      (casesByBarangay.get(key) ?? 0) + cases,
    );
  }

  const rainfallByBarangay = new Map<string, number>();

  for (const row of mRain.rows) {
    const code = row[rainfallBarangayKey];
    const value = row[mrKey];

    if (
      code == null ||
      typeof value !== "number" ||
      !casesByBarangay.has(String(code))
    ) {
      continue;
    }

    const key = String(code);
    rainfallByBarangay.set(
      key,
      (rainfallByBarangay.get(key) ?? 0) + value,
    );
  }

  return [...casesByBarangay.entries()]
    .filter(([code]) => rainfallByBarangay.has(code))
    .map(([code, cases]) => ({
      label: nameOf(code, "barangay"),
      value: rainfallByBarangay.get(code)!,
      cases,
    }))
    .sort((a, b) => b.cases - a.cases);
}, [
  mcSorted,
  mClusters.rows,
  mRain.rows,
  mrKey,
  caseKey,
  clusterBarangayKey,
  rainfallBarangayKey,
  barangayNames,
]);

  const windowGate =
    windowsApi.status === 'ok' && windows.length ? null : windowsApi;

  /* Main cluster records */
  const cRows = clusters.rows;
  const cCasesKey = numKeys(cRows).find((k) => /case/i.test(k));

  const cBarangayKey =
    keysOf(cRows).find(
      (k) => /barangay/i.test(k) && /pcode|code|id/i.test(k),
    ) ?? keysOf(cRows).find((k) => /barangay/i.test(k));

  const cStartKey =
    keysOf(cRows).find((k) => /start/i.test(k) && !isNumKey(cRows, k)) ??
    keysOf(cRows).find((k) => /date/i.test(k) && !isNumKey(cRows, k));

  const latestStart = cStartKey
    ? cRows
        .map((r) => String(r[cStartKey] ?? ''))
        .filter(Boolean)
        .sort()
        .at(-1)
    : undefined;

  const recent = useMemo(() => {
    const rows = [...cRows];

    if (cStartKey) {
      rows.sort((a, b) =>
        String(b[cStartKey]).localeCompare(String(a[cStartKey])),
      );
    }

    return rows.slice(0, 10);
  }, [cRows, cStartKey]);

  const recentCols = useMemo(
    () => makeDisplayColumns(recent, nameOf, 8),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [recent, barangayNames, municipalityNames],
  );

  /* Cluster records over time */
  const otX = timeKey(overTime.rows);
  const otVal = metricKey(overTime.rows, /case|count|cluster|record/i, {
    skip: [otX],
  });

  const otPoints = useMemo(
    () => aggregate(overTime.rows, otX, otVal),
    [overTime.rows, otX, otVal],
  );

  /* Seasonality */
  const seasonX =
    keysOf(season.rows).find((k) => /iso.?week/i.test(k)) ??
    keysOf(season.rows).find((k) => /week/i.test(k)) ??
    timeKey(season.rows);

  const seasonVal = metricKey(
    season.rows,
    /case|count|total|record|cluster/i,
    { skip: [seasonX] },
  );

  const seasonPoints = useMemo(
    () => aggregate(season.rows, seasonX, seasonVal),
    [season.rows, seasonX, seasonVal],
  );

  /* Hazard exposure */
  const hazardMetrics = numKeys(hazard.rows).filter((k) => !SKIP.test(k));
  const hazardKey =
    metricKey(hazard.rows, /case|cluster/i) ?? hazardMetrics[0];
  const hazardLabel = labelKey(hazard.rows);

  const ranked = useMemo(
    () =>
      hazardKey
        ? hazard.rows
            .filter((r) => typeof r[hazardKey] === 'number')
            .map((r) => ({
              label: String(r[hazardLabel] ?? ''),
              value: r[hazardKey] as number,
            }))
            .sort((a, b) => b.value - a.value)
            .slice(0, 10)
        : [],
    [hazard.rows, hazardKey, hazardLabel],
  );

  void seasonPoints;
  void ranked;

  /* Official weekly dengue reports */
  const wCasesKey = metricKey(weekly.rows, /case/i, {
    not: /death/i,
  });

  const wDeathsKey = numKeys(weekly.rows).find((k) => /death/i.test(k));
  const wX = timeKey(weekly.rows);
  const wCases = sum(weekly.rows, wCasesKey);
  const wDeaths = sum(weekly.rows, wDeathsKey);

  const wKey =
    weeklyMetric === 'deaths' && wDeathsKey ? wDeathsKey : wCasesKey;

  const wPoints = useMemo(
    () => (wKey ? aggregate(weekly.rows, wX, wKey) : []),
    [weekly.rows, wX, wKey],
  );

  /* Rainfall */
  const rainKey = metricKey(rain.rows, /rain|precip|mm/i);
  const rainX = timeKey(rain.rows);

  const rainPoints = useMemo(
    () => (rainKey ? aggregate(rain.rows, rainX, rainKey) : []),
    [rain.rows, rainX, rainKey],
  );

  const rainPeak = rainPoints.reduce<Point | null>(
    (b, p) => (!b || p.y > b.y ? p : b),
    null,
  );

  const loading = (s: ApiState) => s.status === 'loading';

  return (
    <div className="min-h-full bg-[#f4f6fb] font-['Montserrat',sans-serif] text-[#1d2648]">
      {/* Title and filters */}
      <div className="sticky top-0 z-10 border-b border-[#e1e6f0] bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-3 px-5 py-4 md:px-8">
          <div className="mr-auto">
            <h1 className="text-xl font-bold tracking-tight text-[#080f43]">
              Laguna disease and flood dashboard
            </h1>
            <p className="text-sm text-[#5d6a91]">
              Dengue and leptospirosis clusters alongside rainfall and flood hazard.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-[#5d6a91]">
                Disease
              </span>
              <Segmented
                value={disease}
                onChange={changeDisease}
                options={DISEASES}
                label="Disease"
              />
            </div>

            <label className="flex items-center gap-2 text-xs font-medium text-[#5d6a91]">
              Period
              <select
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                className="rounded-lg border border-[#e1e6f0] bg-white px-2.5 py-1.5 text-sm font-normal text-[#1d2648] outline-none focus:border-[#3449a3]"
              >
                {PERIODS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl space-y-10 px-5 py-8 md:px-8">
        {/* Overview */}
        <section aria-labelledby="overview">
          <SectionTitle
            id="overview"
            title={`${dName} at a glance`}
            note={`Based on recorded ${disease} clusters, ${periodText}.`}
          />

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi
              label="Clusters recorded"
              value={clusters.status === 'ok' ? num(cRows.length) : '—'}
              hint={`${dName} clusters, ${periodText}`}
              loading={loading(clusters)}
            />

            <Kpi
              label="Cases in clusters"
              value={cCasesKey ? num(sum(cRows, cCasesKey)) : '—'}
              hint="Added up across all clusters"
              loading={loading(clusters)}
            />

            <Kpi
              label="Barangays affected"
              value={cBarangayKey ? num(distinct(cRows, cBarangayKey)) : '—'}
              hint="With at least one cluster"
              loading={loading(clusters)}
            />

            <Kpi
              label="Most recent cluster"
              value={
                latestStart
                  ? formatDate(latestStart.slice(0, 10))
                  : '—'
              }
              hint="Start date of the newest record"
              loading={loading(clusters)}
            />
          </div>
        </section>

        {/* Trends */}
        <section aria-labelledby="trends">
          <SectionTitle id="trends" title="Trends over time" />

          <div className="grid gap-5 lg:grid-cols-2">
            <Card
              title={`${dName} clusters over time`}
              subtitle="Observed records summed across Laguna municipalities"
              state={overTime}
              empty={otPoints.length < 2}
            >
              <XYChart
                kind="line"
                points={otPoints}
                yLabel={otVal ? pretty(otVal) : 'Clusters'}
                xLabel={pretty(otX)}
              />
            </Card>

            <Card
              title="Rainfall per week"
              subtitle={
                rainPeak
                  ? `Laguna-wide. Highest week: ${num(rainPeak.y)} (${formatDate(rainPeak.x.slice(0, 10))})`
                  : 'Laguna-wide weekly rainfall'
              }
              state={rain}
              empty={rainPoints.length < 2}
            >
              <XYChart
                kind="line"
                points={rainPoints}
                yLabel={pretty(rainKey ?? 'Rainfall')}
                xLabel="Week"
              />
            </Card>

            {disease === 'dengue' && (
              <div className="lg:col-span-2">
                <Card
                  title={`Reported dengue ${weeklyMetric} per week`}
                  subtitle={
                    wCasesKey
                      ? `Official weekly Laguna reports. Total in period: ${num(wCases)} cases${wDeathsKey ? `, ${num(wDeaths)} deaths` : ''}`
                      : 'Official weekly Laguna reports'
                  }
                  state={weekly}
                  empty={wPoints.length < 2}
                  controls={
                    wDeathsKey ? (
                      <Segmented
                        value={weeklyMetric}
                        onChange={setWeeklyMetric}
                        label="Metric"
                        options={[
                          { value: 'cases', label: 'Cases' },
                          { value: 'deaths', label: 'Deaths' },
                        ]}
                      />
                    ) : undefined
                  }
                >
                  <XYChart
                    kind="line"
                    points={wPoints}
                    yLabel={`${pretty(weeklyMetric)} per week`}
                    xLabel="Week"
                  />
                </Card>
              </div>
            )}
          </div>
        </section>

        {/* Cluster windows */}
        <section aria-labelledby="windows">
          <SectionTitle
            id="windows"
            title="Cluster windows"
            note="Choose a detection window to see its clusters and rainfall during that period."
          />

          {/* Cards now appear BEFORE the slider */}
          <div className="grid gap-5 lg:grid-cols-2">
            <Card
              title="Largest clusters in this window"
              subtitle={
                win
                  ? `${formatDate(win.start)} to ${formatDate(win.end)}`
                  : undefined
              }
              state={windowGate ?? mClusters}
              empty={mcSorted.length === 0}
            >
              <div className="max-h-80 overflow-auto rounded-lg border border-[#eef1f8]">
                <table className="w-full border-collapse text-left text-sm">
                  <thead className="sticky top-0 bg-[#f7f8fc] text-xs text-[#5d6a91] shadow-[0_1px_0_#eef1f8]">
                    <tr>
                      {mcColumns.map((c) => (
                        <th
                          key={c.key}
                          className="whitespace-nowrap px-3 py-2 font-semibold"
                        >
                          {c.label}
                        </th>
                      ))}
                    </tr>
                  </thead>

                  <tbody>
                    {mcSorted.map((r, i) => (
                      <tr
                        key={i}
                        className="border-t border-[#eef1f8] hover:bg-[#f7f8fc]"
                      >
                        {mcColumns.map((c) => (
                          <td key={c.key} className="whitespace-nowrap px-3 py-2">
                            {c.get(r)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

                <Card
                title="Rainfall in clustered barangays"
                subtitle={
                    mrKey
                    ? `${pretty(mrKey)} for barangays shown in the cluster table`
                    : 'Rainfall for barangays shown in the cluster table'
                }
                state={windowGate ?? mRain}
                empty={mrBars.length === 0}
                >
                <VBarChart
                    items={mrBars}
                    unit={mrKey ? pretty(mrKey) : undefined}
                />
                </Card>
          </div>

          {/* Slider moved below both cards */}
          <div className="mt-5 rounded-2xl border border-[#e1e6f0] bg-white p-5 shadow-[0_8px_30px_rgba(8,15,67,0.05)]">
            {windowsApi.status === 'loading' && (
              <div
                className="h-14 animate-pulse rounded-xl bg-[#f4f6fb] motion-reduce:animate-none"
                aria-label="Loading windows"
              />
            )}

            {windowsApi.status === 'error' && (
              <div>
                <p className="text-sm font-semibold text-[#b3261e]">
                  Could not load cluster windows
                </p>
                <p className="mt-1 text-sm text-[#5d6a91]">
                  {windowsApi.error}
                </p>
                <button
                  onClick={windowsApi.retry}
                  className="mt-3 rounded-lg bg-[#3449a3] px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-[#080f43]"
                >
                  Try again
                </button>
              </div>
            )}

            {windowsApi.status === 'ok' && windows.length === 0 && (
              <p className="text-sm text-[#8390b5]">
                No cluster windows available for {dName.toLowerCase()}.
              </p>
            )}

            {windowsApi.status === 'ok' && win && (
              <div>
                <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  <p className="text-base font-semibold text-[#080f43]">
                    {formatDate(win.start)} to {formatDate(win.end)}
                  </p>
                  <p className="text-xs text-[#8390b5]">
                    Window {winPos + 1} of {windows.length}
                  </p>
                </div>

                <input
                  type="range"
                  min={0}
                  max={Math.max(windows.length - 1, 0)}
                  step={1}
                  value={winPos}
                  disabled={windows.length < 2}
                  onChange={(e) => setWinIdx(Number(e.target.value))}
                  aria-label="Cluster window"
                  aria-valuetext={`${formatDate(win.start)} to ${formatDate(win.end)}`}
                  className="h-2 w-full cursor-pointer accent-[#3449a3] disabled:cursor-not-allowed disabled:opacity-50"
                />

                <div className="mt-2 flex justify-between text-xs text-[#8390b5]">
                  <span>{formatDate(windows[0].start)}</span>
                  <span>{formatDate(windows[windows.length - 1].end)}</span>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Cluster records */}
        <section aria-labelledby="records">
          <SectionTitle id="records" title="Cluster records" />

          <Card
            title={`Latest ${disease} clusters`}
            subtitle={
              clusters.status === 'ok'
                ? `Showing ${recent.length} of ${num(cRows.length)} records, newest first`
                : undefined
            }
            state={clusters}
            empty={recent.length === 0}
          >
            <div className="overflow-x-auto rounded-lg border border-[#eef1f8]">
              <table className="w-full border-collapse text-left text-sm">
                <thead className="bg-[#f7f8fc] text-xs text-[#5d6a91]">
                  <tr>
                    {recentCols.map((c) => (
                      <th
                        key={c.key}
                        className="whitespace-nowrap px-3 py-2 font-semibold"
                      >
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {recent.map((r, i) => (
                    <tr
                      key={i}
                      className="border-t border-[#eef1f8] hover:bg-[#f7f8fc]"
                    >
                      {recentCols.map((c) => (
                        <td key={c.key} className="whitespace-nowrap px-3 py-2">
                          {c.get(r)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </section>

        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-[#e1e6f0] pt-5 text-xs text-[#8390b5]">
          <span>Data served live from the EpiFlood API.</span>
          <Link
            to="/exploredatasets"
            className="font-medium text-[#3449a3] hover:underline"
          >
            Browse the API documentation
          </Link>
        </footer>
      </div>
    </div>
  );
}

/* --------------------------------- layout components --------------------------------- */

function SectionTitle({
  id,
  title,
  note,
}: {
  id: string;
  title: string;
  note?: string;
}) {
  return (
    <div className="mb-4">
      <h2 id={id} className="text-lg font-bold tracking-tight text-[#080f43]">
        {title}
      </h2>
      {note && <p className="mt-0.5 text-xs text-[#8390b5]">{note}</p>}
    </div>
  );
}

function Kpi({
  label,
  value,
  hint,
  loading,
}: {
  label: string;
  value: string;
  hint: string;
  loading: boolean;
}) {
  return (
    <div className="rounded-2xl border border-[#e1e6f0] bg-white p-5 shadow-[0_8px_30px_rgba(8,15,67,0.05)]">
      <p className="text-sm font-medium text-[#5d6a91]">{label}</p>

      {loading ? (
        <div className="mt-2 h-9 w-24 animate-pulse rounded-md bg-[#eef1ff] motion-reduce:animate-none" />
      ) : (
        <p className="mt-1 text-3xl font-bold tracking-tight text-[#080f43]">
          {value}
        </p>
      )}

      <p className="mt-1 text-xs text-[#8390b5]">{hint}</p>
    </div>
  );
}

function Card({
  title,
  subtitle,
  controls,
  state,
  empty,
  children,
}: {
  title: string;
  subtitle?: string;
  controls?: ReactNode;
  state: ApiState & { retry: () => void };
  empty?: boolean;
  children: ReactNode;
}) {
  return (
    <article className="rounded-2xl border border-[#e1e6f0] bg-white p-5 shadow-[0_8px_30px_rgba(8,15,67,0.05)]">
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-[#080f43]">{title}</h3>
          {subtitle && (
            <p className="mt-0.5 text-xs text-[#8390b5]">{subtitle}</p>
          )}
        </div>
        {controls}
      </header>

      {state.status === 'loading' && (
        <div
          className="h-56 animate-pulse rounded-xl bg-[#f4f6fb] motion-reduce:animate-none"
          aria-label="Loading"
        />
      )}

      {state.status === 'error' && (
        <div className="rounded-xl bg-[#fdf3f2] p-4">
          <p className="text-sm font-semibold text-[#b3261e]">
            Could not load this data
          </p>
          <p className="mt-1 text-sm text-[#5d6a91]">{state.error}</p>
          <button
            onClick={state.retry}
            className="mt-3 rounded-lg bg-[#3449a3] px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-[#080f43]"
          >
            Try again
          </button>
        </div>
      )}

      {state.status === 'ok' &&
        (empty ? (
          <p className="py-10 text-center text-sm text-[#8390b5]">
            No data for this selection.
          </p>
        ) : (
          children
        ))}
    </article>
  );
}

function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  label: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="inline-flex rounded-lg bg-[#f4f6fb] p-0.5"
    >
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={`rounded-md px-3 py-1 text-xs transition ${
            value === o.value
              ? 'bg-white font-semibold text-[#3449a3] shadow-sm'
              : 'text-[#5d6a91] hover:text-[#3449a3]'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------- charts ------------------------------------- */

function VBarChart({
  items,
  unit,
  scaleMax,
}: {
  items: { label: string; value: number }[];
  unit?: string;
  scaleMax?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);

  const W = 640;
  const H = 340;
  const L = 48;
  const R = 12;
  const T = 16;
  const B = 110;

  const n = items.length;
  const max = Math.max(...items.map((i) => i.value), scaleMax ?? 0, 1);
  const step = Math.pow(10, Math.floor(Math.log10(max)));
  const top = Math.ceil(max / step) * step;
  const plotW = W - L - R;
  const slot = plotW / n;
  const barW = Math.min(slot * 0.7, 48);

  const sx = (i: number) => L + slot * (i + 0.5);
  const sy = (v: number) => T + (1 - v / top) * (H - T - B);
  const ticks = Array.from({ length: 5 }, (_, i) => (top * i) / 4);
  const short = (s: string) => (s.length > 20 ? `${s.slice(0, 19)}…` : s);

  return (
    <figure className="relative">
      {unit && (
        <figcaption className="mb-1 text-xs font-medium text-[#5d6a91]">
          {unit}
        </figcaption>
      )}

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={`Vertical bar chart${unit ? `: ${unit}` : ''}`}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((t, k) => (
          <g key={k}>
            <line
              x1={L}
              x2={W - R}
              y1={sy(t)}
              y2={sy(t)}
              stroke="#e8ecf6"
            />
            <text
              x={L - 8}
              y={sy(t) + 4}
              textAnchor="end"
              fontSize="11"
              fill="#8390b5"
            >
              {compact.format(t)}
            </text>
          </g>
        ))}

        {items.map((it, i) => (
          <g key={i} onMouseEnter={() => setHover(i)}>
            <rect
              x={sx(i) - slot / 2}
              y={T}
              width={slot}
              height={H - T - B}
              fill="transparent"
            />

            <rect
              x={sx(i) - barW / 2}
              y={sy(it.value)}
              width={barW}
              height={Math.max(sy(0) - sy(it.value), 1)}
              rx={Math.min(3, barW / 2)}
              fill={BLUE}
              opacity={hover === null || hover === i ? 1 : 0.45}
            />

            <text
              x={sx(i)}
              y={H - B + 14}
              transform={`rotate(-40 ${sx(i)} ${H - B + 14})`}
              textAnchor="end"
              fontSize="11"
              fill={hover === i ? '#080f43' : '#5d6a91'}
            >
              <title>{it.label}</title>
              {short(it.label)}
            </text>
          </g>
        ))}
      </svg>

      {hover !== null && items[hover] && (
        <div
          className="pointer-events-none absolute top-6 rounded-lg bg-[#080f43] px-3 py-2 text-xs text-white shadow-lg"
          style={{
            left: `${(sx(hover) / W) * 100}%`,
            transform: `translateX(${hover > n / 2 ? '-110%' : '10%'})`,
          }}
        >
          <div className="font-semibold">{items[hover].label}</div>
          <div>{num(items[hover].value)}</div>
        </div>
      )}
    </figure>
  );
}

function XYChart({
  kind,
  points,
  yLabel,
  xLabel,
}: {
  kind: 'line' | 'bar';
  points: Point[];
  yLabel?: string;
  xLabel?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);

  const W = 640;
  const H = 260;
  const L = 44;
  const R = 12;
  const T = 10;
  const B = 28;

  const n = points.length;
  const min = Math.min(0, ...points.map((p) => p.y));
  const max = Math.max(...points.map((p) => p.y), 1);
  const step = Math.pow(10, Math.floor(Math.log10(max - min || 1)));
  const top = Math.ceil(max / step) * step;
  const plotW = W - L - R;
  const slot = plotW / n;

  const sx = (i: number) =>
    kind === 'bar'
      ? L + slot * (i + 0.5)
      : L + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);

  const sy = (v: number) =>
    T + (1 - (v - min) / (top - min || 1)) * (H - T - B);

  const ticks = Array.from(
    { length: 5 },
    (_, i) => min + ((top - min) * i) / 4,
  );

  const every = Math.max(1, Math.ceil(n / 8));
  const barW = Math.max(slot * 0.7, 1);

  const onMove = (e: MouseEvent<SVGSVGElement>) => {
    if (!n) return;

    const box = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - box.left) / box.width) * W;

    const i =
      kind === 'bar'
        ? Math.floor((x - L) / slot)
        : Math.round(((x - L) / plotW) * (n - 1));

    setHover(Math.max(0, Math.min(n - 1, i)));
  };

  const line = points.map((p, i) => `${sx(i)},${sy(p.y)}`).join(' ');

  return (
    <figure className="relative">
      {yLabel && (
        <figcaption className="mb-1 text-xs font-medium text-[#5d6a91]">
          {yLabel}
        </figcaption>
      )}

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        role="img"
        aria-label={`${kind} chart${yLabel ? `: ${yLabel}` : ''}`}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={L}
              x2={W - R}
              y1={sy(t)}
              y2={sy(t)}
              stroke="#e8ecf6"
            />
            <text
              x={L - 8}
              y={sy(t) + 4}
              textAnchor="end"
              fontSize="11"
              fill="#8390b5"
            >
              {compact.format(t)}
            </text>
          </g>
        ))}

        {points.map((p, i) =>
          i % every === 0 ? (
            <text
              key={i}
              x={sx(i)}
              y={H - 8}
              textAnchor="middle"
              fontSize="11"
              fill="#8390b5"
            >
              {p.x.slice(0, 10)}
            </text>
          ) : null,
        )}

        {kind === 'line' && n > 0 && (
          <>
            <polygon
              points={`${sx(0)},${sy(min)} ${line} ${sx(n - 1)},${sy(min)}`}
              fill={BLUE}
              opacity="0.08"
            />
            <polyline
              points={line}
              fill="none"
              stroke={BLUE}
              strokeWidth="2"
              strokeLinejoin="round"
            />
          </>
        )}

        {kind === 'bar' &&
          points.map((p, i) => (
            <rect
              key={i}
              x={sx(i) - barW / 2}
              y={Math.min(sy(0), sy(p.y))}
              width={Math.max(barW - 1, 1)}
              height={Math.max(Math.abs(sy(0) - sy(p.y)), 1)}
              rx={Math.min(3, barW / 2)}
              fill={BLUE}
              opacity={hover === null || hover === i ? 1 : 0.45}
            />
          ))}

        {hover !== null && kind === 'line' && points[hover] && (
          <g>
            <line
              x1={sx(hover)}
              x2={sx(hover)}
              y1={T}
              y2={H - B}
              stroke={BLUE}
              strokeDasharray="3 3"
              opacity="0.5"
            />
            <circle
              cx={sx(hover)}
              cy={sy(points[hover].y)}
              r="4"
              fill="#fff"
              stroke={BLUE}
              strokeWidth="2"
            />
          </g>
        )}
      </svg>

      {xLabel && (
        <p className="text-center text-xs text-[#8390b5]">{xLabel}</p>
      )}

      {hover !== null && points[hover] && (
        <div
          className="pointer-events-none absolute top-6 rounded-lg bg-[#080f43] px-3 py-2 text-xs text-white shadow-lg"
          style={{
            left: `${(sx(hover) / W) * 100}%`,
            transform: `translateX(${hover > n / 2 ? '-110%' : '10%'})`,
          }}
        >
          <div className="font-semibold">
            {xLabel ? `${xLabel} ` : ''}
            {formatDate(points[hover].x.slice(0, 10))}
          </div>
          <div>{num(points[hover].y)}</div>
        </div>
      )}
    </figure>
  );
}
