import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { consumeFanCatalog } from './fan-catalog.mjs';
import type { FanCatalog } from './fan-catalog.mjs';

type CatalogState = { catalog: FanCatalog | null; loading: boolean; error: boolean };
const CatalogContext = createContext<(CatalogState & { retry: () => void }) | null>(null);

/** One validated public projection per app session; no internal-data fallback. */
export function PublicFanCatalog({ children, initialProjection }: { children: ReactNode; initialProjection?: unknown }) {
  const [state, setState] = useState<CatalogState>(() => initialProjection === undefined
    ? { catalog: null, loading: true, error: false }
    : { catalog: consumeFanCatalog(initialProjection), loading: false, error: false });
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  useEffect(() => {
    if (initialProjection !== undefined) return;
    let active = true;
    setState({ catalog: null, loading: true, error: false });
    void fetch('/data/match-library-strict-public.json', { headers: { Accept: 'application/json' } })
      .then((response) => { if (!response.ok) throw new Error('public-catalog-unavailable'); return response.json(); })
      .then((input) => { const catalog = consumeFanCatalog(input); if (active) setState({ catalog, loading: false, error: false }); })
      .catch(() => { if (active) setState({ catalog: null, loading: false, error: true }); });
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
