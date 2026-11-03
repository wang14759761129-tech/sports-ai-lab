import { buildFanWatchRouteCandidates } from './fan-watch-routing.mjs';

/** Saved identities survive catalog changes. Watching still goes through the existing Watch route. */
export function createCollectorCards(catalog, savedMatchIds) {
  return savedMatchIds.map((matchId) => {
    const match = catalog?.matches.find((item) => item.match_id === matchId) ?? null;
    const watchSource = match?.match_video_link_status === 'HUMAN_VERIFIED'
      ? catalog.sources.find((source) => match.video_source_ids.includes(source.source_id)
        && source.canonical_match_id === matchId && source.match_link_status === 'HUMAN_VERIFIED'
        && source.url && buildFanWatchRouteCandidates(source).some((route) => route.mode === 'OFFICIAL_PAGE'
          && route.sourceReference === 'VERIFIED' && route.viewingPermission === 'PUBLIC_PLATFORM_PAGE')) ?? null
      : null;
    return { match_id: matchId, match, watch_source: watchSource,
      result: match?.result_status === 'OFFICIAL_EVENT_RESULT_CROSSCHECKED' ? match.recorded_result : null };
  });
}

/** Only remove the selected saved identity; all personal notes and follows remain intact. */
export function removeCollectorMatch(data, matchId) {
  return { ...data, saved_match_ids: data.saved_match_ids.filter((id) => id !== matchId) };
}
