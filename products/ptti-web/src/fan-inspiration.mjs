import schema from './contracts/fan-inspiration-v0.1.schema.json' with { type: 'json' };
import { normalizeFanSearch } from './fan-catalog.mjs';

export const FAN_INSPIRATION_SHA = '702bc12850676ae9eeda39b533ade9cc5f2da0fe8710aa8ebc82f0c2b803c5c9';
export const FAN_INSPIRATION_MAIN_COMMIT = '753edfbd1b95bc85881bdc7632e6df14a09fdc24';
const requireValue = (ok, code) => { if (!ok) throw Error(code); };

// Implements the constraints used by the pinned Main schema; not a general JSON Schema engine.
export function validateInspirationSchema(value, node = schema, path = '$') {
  if (node.$ref) return validateInspirationSchema(value, schema.$defs[node.$ref.split('/').at(-1)], path);
  if (Object.hasOwn(node, 'const')) requireValue(value === node.const, `inspiration-const:${path}`);
  if (node.enum) requireValue(node.enum.includes(value), `inspiration-enum:${path}`);
  const types = node.type ? [].concat(node.type) : [];
  const type = value === null ? 'null' : Array.isArray(value) ? 'array' : typeof value;
  if (types.length) requireValue(types.includes(type) || (types.includes('integer') && Number.isInteger(value)), `inspiration-type:${path}`);
  if (typeof value === 'string') {
    if (node.minLength !== undefined) requireValue(value.length >= node.minLength, `inspiration-length:${path}`);
    if (node.pattern) requireValue(new RegExp(node.pattern).test(value), `inspiration-pattern:${path}`);
    if (node.format === 'uri') { const u = new URL(value); requireValue(u.protocol === 'https:' && !u.username && !u.password, `inspiration-url:${path}`); }
    if (node.format === 'date' || node.format === 'date-time') {
      requireValue(Number.isFinite(Date.parse(value)), `inspiration-date:${path}`);
      if (node.format === 'date') requireValue(/^\d{4}-\d{2}-\d{2}$/.test(value) && new Date(value).toISOString().slice(0, 10) === value, `inspiration-date:${path}`);
      else requireValue(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)
        && new Date(`${value.slice(0, 10)}T00:00:00Z`).toISOString().slice(0, 10) === value.slice(0, 10), `inspiration-date:${path}`);
    }
  }
  if (typeof value === 'number') {
    if (node.minimum !== undefined) requireValue(value >= node.minimum, `inspiration-minimum:${path}`);
    if (node.maximum !== undefined) requireValue(value <= node.maximum, `inspiration-maximum:${path}`);
  }
  if (Array.isArray(value)) {
    if (node.minItems !== undefined) requireValue(value.length >= node.minItems, `inspiration-count:${path}`);
    if (node.maxItems !== undefined) requireValue(value.length <= node.maxItems, `inspiration-count:${path}`);
    if (node.uniqueItems) requireValue(new Set(value.map((item) => JSON.stringify(item))).size === value.length, `inspiration-duplicate:${path}`);
    if (node.items) value.forEach((item, i) => validateInspirationSchema(item, node.items, `${path}[${i}]`));
  } else if (value && typeof value === 'object') {
    for (const key of node.required ?? []) requireValue(Object.hasOwn(value, key), `inspiration-missing:${path}.${key}`);
    for (const [key, item] of Object.entries(value)) {
      if (Object.hasOwn(node.properties ?? {}, key)) validateInspirationSchema(item, node.properties[key], `${path}.${key}`);
      else requireValue(node.additionalProperties !== false, `inspiration-extra:${path}.${key}`);
    }
  }
  return value;
}

export function consumeFanInspiration(input, catalog) {
  validateInspirationSchema(input);
  requireValue(input.input_identity.base_sha256 === '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930'
    && input.input_identity.goal17_delta_sha256 === '6f05d1fc48fb74ffc305abe20fd9152973bd96bb009fe6a183d42c031a31198a'
    && input.input_identity.goal22_supplement_sha256 === '43136eace93e9650ec73dd589abda00ee46addcaf80160b9bfc17250aeaa28db', 'inspiration-input-identity');
  const ids = new Set(); const urls = new Set();
  for (const item of [...input.clips, ...input.match_watch_sources]) {
    requireValue(!ids.has(item.source_id) && !urls.has(item.original_url), 'inspiration-duplicate-source'); ids.add(item.source_id); urls.add(item.original_url);
    const videoId = item.original_url && new URL(item.original_url).searchParams.get('v');
    requireValue(item.source_id.endsWith(`:${videoId}`) && /^[\w-]{11}$/.test(videoId), 'inspiration-source-url-id');
    requireValue(item.publisher_url === 'https://www.youtube.com/@wttglobal', 'inspiration-publisher-url');
    const old = catalog.sources.find((source) => source.source_id === item.source_id);
    if (old) requireValue(old.url === item.original_url && old.canonical_match_id === item.match_id, 'inspiration-existing-source-mismatch');
    if (input.clips.includes(item)) requireValue(item.match_id === null && item.athlete_ids.length === 0 && item.athlete_association_status === 'UNASSIGNED_EVENT_LEVEL'
      && ['EVENT_HIGHLIGHTS_TITLE_CLAIM', 'SEASON_HIGHLIGHTS_TITLE_CLAIM'].includes(item.video_category), 'inspiration-highlight-scope');
    else requireValue(Boolean(old) && catalog.matches.some((match) => match.match_id === item.match_id && match.video_source_ids.includes(item.source_id)), 'inspiration-match-source-mismatch');
  }
  requireValue(catalog.sources.every((source) => ids.has(source.source_id)), 'inspiration-baseline-missing');
  for (const reaction of input.international_reactions) requireValue(catalog.matches.some((match) => match.match_id === reaction.related_match_id)
    && new URL(reaction.source_url).hostname === 'www.lemonde.fr', 'inspiration-reaction-scope');
  for (const dossier of input.gear_dossiers) {
    const match = catalog.matches.find((match) => match.match_id === dossier.match_id);
    requireValue(Boolean(match), 'inspiration-gear-match');
    requireValue(new Set(dossier.participants.map((person) => person.athlete_id)).size === dossier.participants.length, 'inspiration-gear-duplicate-athlete');
    for (const person of dossier.participants) {
      const star = catalog.stars.find((star) => star.athlete_id === person.athlete_id);
      if (star) requireValue(normalizeFanSearch(star.name_en) === normalizeFanSearch(person.athlete_name), 'inspiration-gear-athlete-name');
      // Validate Main's explicit assertion against the roster; never fill or rewrite a baseline athlete ID.
      requireValue(match.participants.some((p) => p.athlete_id && p.athlete_id === person.athlete_id
        || p.athlete_id === null && star && normalizeFanSearch(p.name_en) === normalizeFanSearch(person.athlete_name)), 'inspiration-gear-athlete');
      requireValue(new Set(person.items.map((item) => item.category)).size === 4, 'inspiration-gear-categories');
    }
  }
  requireValue(new Set(input.gear_dossiers.map((dossier) => dossier.match_id)).size === input.gear_dossiers.length, 'inspiration-duplicate-dossier');
  requireValue(new Set(input.international_reactions.map((row) => row.reaction_id)).size === input.international_reactions.length, 'inspiration-duplicate-reaction');
  requireValue(new Set(input.watch_routes.map((route) => route.mode)).size === 5, 'inspiration-watch-modes');
  for (const route of input.watch_routes) requireValue(route.source_ids.every((id) => ids.has(id)), 'inspiration-route-source');
  return input;
}

export function applyFanInspiration(catalog, raw) {
  const inspiration = consumeFanInspiration(raw, catalog);
  const sources = [...catalog.sources];
  for (const item of inspiration.clips) {
    if (sources.some((source) => source.source_id === item.source_id)) continue;
    sources.push({ source_id: item.source_id, title: item.original_title, display_title_zh: null, event: item.event_name ?? '', event_zh: null,
      round: '', round_zh: null, event_year: item.event_year, match_type: 'UNKNOWN', participants_claimed: {}, platform: item.platform,
      video_id: new URL(item.original_url).searchParams.get('v'), watch_entry: 'OPEN_OFFICIAL_PLATFORM_URL', url: item.original_url,
      publisher: item.publisher, publisher_url: item.publisher_url, source_verified_at: item.verification.metadata_checked_at,
      external_viewing: 'ALLOWED', thumbnail_display: 'NOT_ALLOWED', embedding: 'UNKNOWN', source_identity_status: item.verification.source_identity,
      publisher_identity_status: item.verification.publisher_identity, content_type_claim: 'HIGHLIGHTS', completeness_status: 'UNVERIFIED',
      territory: 'UNKNOWN', recorded_playback_status: 'NOT_TESTED', current_session_eligibility: 'NOT_EVALUATED_CURRENT_SESSION',
      canonical_match_id: null, match_link_status: 'UNKNOWN', evidence_source_ids: [], inspiration_category: item.video_category });
  }
  return { catalog: { ...catalog, sources }, inspiration };
}
