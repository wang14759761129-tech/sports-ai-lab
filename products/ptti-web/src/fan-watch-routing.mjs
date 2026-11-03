const ROUTES = ['OFFICIAL_EMBED', 'OFFICIAL_PAGE', 'AUTHORIZED_SOURCE', 'REPLAY', 'LIVE_SCORE'];

function hasVerifiedReference(source) {
  const sourceIsVerified = source?.source_identity_status === 'VERIFIED'
    || source?.source_identity_status === 'VERIFIED_FROM_OFFICIAL_VIDEO_METADATA';
  const publisherIsVerified = source?.publisher_identity_status === 'VERIFIED'
    || source?.publisher_identity_status === 'VERIFIED_OFFICIAL_CHANNEL';
  if (!sourceIsVerified || !publisherIsVerified || typeof source.source_verified_at !== 'string') return false;
  return Number.isFinite(Date.parse(source.source_verified_at));
}

function publicPagePermission(source) {
  if (source?.external_viewing === 'ALLOWED') return 'PUBLIC_PLATFORM_PAGE';
  if (source?.external_viewing === 'NOT_ALLOWED') return 'DENIED';
  return 'UNKNOWN';
}

/** Map only fields present in the public Match Library projection to the
 * Playback routing contract. Missing route types remain UNKNOWN and blocked. */
export function buildFanWatchRouteCandidates(source) {
  const sourceReference = hasVerifiedReference(source) ? 'VERIFIED' : 'UNKNOWN';
  const viewingPermission = publicPagePermission(source);
  const platformPageType = source?.watch_entry === 'OPEN_OFFICIAL_PLATFORM_URL' ? 'OFFICIAL_PAGE' : undefined;

  return [
    { mode: 'OFFICIAL_EMBED', sourceReference, viewingPermission, playbackEvidence: 'NOT_TESTED', playbackType: 'OFFICIAL_EMBED', embedPermission: source?.embedding === 'ALLOWED' ? 'ALLOWED' : source?.embedding === 'NOT_ALLOWED' ? 'DENIED' : 'UNKNOWN' },
    { mode: 'OFFICIAL_PAGE', sourceReference, viewingPermission, playbackEvidence: 'NOT_TESTED', ...(platformPageType ? { playbackType: platformPageType } : {}) },
    // Match Library v0.1 contains no authorized-stream or authorized-replay
    // grant. These modes therefore stay blocked unless a later contract adds it.
    { mode: 'AUTHORIZED_SOURCE', sourceReference, viewingPermission: 'UNKNOWN' },
    { mode: 'REPLAY', sourceReference, viewingPermission: 'UNKNOWN' },
    // No live-score source is represented in the current public projection.
    { mode: 'LIVE_SCORE', sourceReference, viewingPermission: 'UNKNOWN', liveScore: 'UNKNOWN' },
  ];
}

export function evaluateFanWatchRoutes(source, evaluateWatchRoute) {
  if (typeof evaluateWatchRoute !== 'function') throw new TypeError('watch-route-evaluator-required');
  return buildFanWatchRouteCandidates(source).map((candidate) => {
    const decision = evaluateWatchRoute(candidate);
    const url = candidate.mode === 'OFFICIAL_PAGE' && decision?.state === 'ELIGIBLE' && typeof source?.url === 'string'
      ? source.url
      : null;
    return { mode: candidate.mode, decision, url };
  });
}

export const FAN_WATCH_ROUTE_MODES = ROUTES;
