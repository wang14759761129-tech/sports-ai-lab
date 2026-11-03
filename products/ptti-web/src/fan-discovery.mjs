import { filterFanSources } from './fan-catalog.mjs';

/** Only admitted short clips and event highlights. No title-based athlete or training inference. */
export function discoverFanContent(catalog, { query = '', platform = 'all', athleteId = 'all', event = 'all', trainingType = 'all', contentType = 'all' } = {}) {
  const kinds = new Set(['CLIP', 'HIGHLIGHTS']);
  if (contentType !== 'all' && !kinds.has(contentType)) return [];
  // The current Main catalog has no verified training taxonomy.
  if (!['all', 'UNKNOWN'].includes(trainingType)) return [];
  return filterFanSources(catalog, { query, contentType }).filter((source) => {
    if (!kinds.has(source.content_type_claim) || source.external_viewing !== 'ALLOWED' || !source.url) return false;
    if (platform !== 'all' && source.platform !== platform) return false;
    if (event !== 'all' && source.event !== event) return false;
    if (athleteId === 'all') return true;
    if (source.match_link_status !== 'HUMAN_VERIFIED' || !source.canonical_match_id) return false;
    const match = catalog?.matches.find((item) => item.match_id === source.canonical_match_id && item.video_source_ids.includes(source.source_id));
    return Boolean(match?.participants.some((person) => person.athlete_id === athleteId));
  });
}
