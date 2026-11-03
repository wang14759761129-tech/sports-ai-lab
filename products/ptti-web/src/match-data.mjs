/** Validate the JSON shape consumed by the UI; never rewrite source or rights facts. */
export function parseMatchRecords(data) {
  const strings = ['id', 'event', 'eventCategory', 'round', 'platform', 'regionRestriction', 'lastVerifiedAt', 'note'];
  const enums = { discipline: ['MS', 'WS', 'MD', 'WD', 'XD'], routeType: ['video-page', 'event-page', 'source-only'], sourceStatus: ['official-listing-found', 'no-verified-route'], playbackStatus: ['PLAYBACK_PASS', 'PLAYBACK_FAIL', 'RESTRICTED', 'NOT_TESTED'] };
  if (!Array.isArray(data) || data.some(record => {
    if (!record || typeof record !== 'object' || Array.isArray(record)) return true;
    if (strings.some(key => typeof record[key] !== 'string') || !record.id) return true;
    if (Object.entries(enums).some(([key, values]) => !values.includes(record[key]))) return true;
    if (!Array.isArray(record.players) || !record.players.length || record.players.some(player => typeof player !== 'string')) return true;
    if (!Array.isArray(record.sourceEvidence) || record.sourceEvidence.some(url => typeof url !== 'string')) return true;
    if (!Number.isFinite(record.eventYear) || typeof record.playbackTested !== 'boolean') return true;
    if (record.embedAllowed !== null && typeof record.embedAllowed !== 'boolean') return true;
    if (['platformUrl', 'videoOriginalUrl'].some(key => record[key] !== null && typeof record[key] !== 'string')) return true;
    if (record.result !== undefined && typeof record.result !== 'string') return true;
    return record.playbackEvidence !== undefined && (!record.playbackEvidence || typeof record.playbackEvidence !== 'object' || Array.isArray(record.playbackEvidence));
  }) || new Set(data.map(record => record.id)).size !== data.length) {
    throw new Error('Invalid match list');
  }
  return data;
}
