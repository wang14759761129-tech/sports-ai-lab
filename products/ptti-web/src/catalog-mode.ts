export const catalogMode: 'review' | 'public' = __PTTI_CATALOG_MODE__;
export const isLocalReleaseCandidate = __PTTI_LOCAL_RC__;
export const catalogUrl = catalogMode === 'review' ? '/__ptti/bridge.json' : '/data/web-strict-public.json';
