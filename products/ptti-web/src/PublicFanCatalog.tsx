import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { consumeFanCatalog } from './fan-catalog.mjs';
import { applyGoal17MatchAdditions } from './goal17-match-additions.mjs';
import type { FanCatalog } from './fan-catalog.mjs';
import { applyFanInspiration, FAN_INSPIRATION_SHA } from './fan-inspiration.mjs';
import type { FanInspirationV01 } from './contracts/fan-inspiration-v0.1';
import { consumeMatchReportEvidence, MATCH_REPORT_EVIDENCE_SHA } from './match-report-evidence.mjs';
import type { MainMatchReportV01 } from './contracts/match-report-evidence-v0.1';

type CatalogState = {
  catalog: FanCatalog | null; inspiration: FanInspirationV01 | null; loading: boolean; error: boolean;
  matchReports: MainMatchReportV01[]; matchReportsLoading: boolean; matchReportsError: boolean;
};
const hashes = {
  base: '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930',
  delta: '6f05d1fc48fb74ffc305abe20fd9152973bd96bb009fe6a183d42c031a31198a',
};
async function fetchPinnedJson(path: string, expectedSha: string): Promise<unknown> {
  const response = await fetch(path, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('public-catalog-unavailable');
  const bytes = await response.arrayBuffer();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
    .map((value) => value.toString(16).padStart(2, '0')).join('');
  if (digest !== expectedSha) throw new Error('public-catalog-sha-mismatch');
  return JSON.parse(new TextDecoder().decode(bytes));
}
const CatalogContext = createContext<(CatalogState & { retry: () => void }) | null>(null);

/** One validated public projection per app session; no internal-data fallback. */
export function PublicFanCatalog({ children, initialProjection, initialInspiration, initialAdditions, initialMatchReports }: { children: ReactNode; initialProjection?: unknown; initialInspiration?: unknown; initialAdditions?: unknown; initialMatchReports?: unknown }) {
  const [state, setState] = useState<CatalogState>(() => initialProjection === undefined
    ? { catalog: null, inspiration: null, loading: true, error: false, matchReports: [], matchReportsLoading: true, matchReportsError: false }
    : (() => {
      const base = consumeFanCatalog(initialProjection);
      const catalog = initialAdditions === undefined ? base : applyGoal17MatchAdditions(base, initialAdditions);
      const result = initialInspiration === undefined ? { catalog, inspiration: null } : applyFanInspiration(catalog, initialInspiration);
      return {
        ...result, loading: false, error: false,
        matchReports: initialMatchReports === undefined ? [] : consumeMatchReportEvidence(initialMatchReports, result.catalog),
        matchReportsLoading: false, matchReportsError: false,
      };
    })());
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  useEffect(() => {
    if (initialProjection !== undefined) return;
    let active = true;
    setState({ catalog: null, inspiration: null, loading: true, error: false, matchReports: [], matchReportsLoading: true, matchReportsError: false });
    void Promise.all([
      fetchPinnedJson('/data/match-library-strict-public.json', hashes.base),
      fetchPinnedJson('/data/goal17-official-match-video-additions.json', hashes.delta),
      fetchPinnedJson('/data/fan-inspiration-v0.1.json', FAN_INSPIRATION_SHA),
    ])
      .then(([input, additions, inspiration]) => {
        const result = applyFanInspiration(applyGoal17MatchAdditions(consumeFanCatalog(input), additions), inspiration);
        if (active) setState({ ...result, loading: false, error: false, matchReports: [], matchReportsLoading: true, matchReportsError: false });
        void fetchPinnedJson('/data/match-reports-v0.1.json', MATCH_REPORT_EVIDENCE_SHA)
          .then((reports) => consumeMatchReportEvidence(reports, result.catalog))
          .then((matchReports) => { if (active) setState((current) => ({ ...current, matchReports, matchReportsLoading: false, matchReportsError: false })); })
          .catch(() => { if (active) setState((current) => ({ ...current, matchReports: [], matchReportsLoading: false, matchReportsError: true })); });
      })
      .catch(() => { if (active) setState({ catalog: null, inspiration: null, loading: false, error: true, matchReports: [], matchReportsLoading: false, matchReportsError: false }); });
    return () => { active = false; };
  }, [attempt, initialProjection]);
  const value = useMemo(() => ({ ...state, retry }), [state, retry]);
  return <CatalogContext.Provider value={value}>{children}</CatalogContext.Provider>;
}

export function usePublicFanCatalog() {
  const value = useContext(CatalogContext);
  if (!value) throw new Error('public-fan-catalog-provider-required');
  return value;
}
