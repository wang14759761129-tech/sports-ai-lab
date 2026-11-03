import schema from './contracts/match-experience-delta-v0.1.schema.json' with { type: 'json' };
import { consumeFanCatalog } from './fan-catalog.mjs';

export const MATCH_EXPERIENCE_SHA = '9c3662e8bf13fc8c49b37f3826094d744297f938361afba54945ab91fb1a930a';
export const MATCH_EXPERIENCE_MAIN_COMMIT = '2dcfc49e23101194f74f6f58b544001f728ab00f';
export const MATCH_EXPERIENCE_BASE_SHA = '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930';
const requireValue = (ok, message) => { if (!ok) throw new Error(`match-experience:${message}`); };

// Only the keywords used by this pinned, closed Main schema are supported.
export function validateMatchExperienceDelta(value, node = schema, path = '$') {
  if (node.$ref) return validateMatchExperienceDelta(value, schema.$defs[node.$ref.split('/').at(-1)], path);
  if (Object.hasOwn(node, 'const')) requireValue(JSON.stringify(value) === JSON.stringify(node.const), `const:${path}`);
  if (node.enum) requireValue(node.enum.includes(value), `enum:${path}`);
  const type = value === null ? 'null' : Array.isArray(value) ? 'array' : typeof value;
  if (node.type) requireValue([].concat(node.type).includes(type), `type:${path}`);
  if (typeof value === 'string') {
    if (node.minLength !== undefined) requireValue(value.length >= node.minLength, `length:${path}`);
    if (node.pattern) requireValue(new RegExp(node.pattern).test(value), `pattern:${path}`);
    if (node.format === 'uri') { const url = new URL(value); requireValue(url.protocol === 'https:' && !url.username && !url.password, `url:${path}`); }
    if (node.format === 'date-time') requireValue(/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value)), `date:${path}`);
  }
  if (Array.isArray(value)) {
    if (node.minItems !== undefined) requireValue(value.length >= node.minItems, `count:${path}`);
    if (node.maxItems !== undefined) requireValue(value.length <= node.maxItems, `count:${path}`);
    if (node.uniqueItems) requireValue(new Set(value.map((row) => JSON.stringify(row))).size === value.length, `duplicate:${path}`);
    if (node.items) value.forEach((row, index) => validateMatchExperienceDelta(row, node.items, `${path}[${index}]`));
  } else if (value && typeof value === 'object') {
    for (const key of node.required ?? []) requireValue(Object.hasOwn(value, key), `missing:${path}.${key}`);
    for (const [key, row] of Object.entries(value)) {
      if (Object.hasOwn(node.properties ?? {}, key)) validateMatchExperienceDelta(row, node.properties[key], `${path}.${key}`);
      else requireValue(node.additionalProperties !== false, `extra:${path}.${key}`);
    }
  }
  return value;
}

/** Merge only into the pinned raw public projection, before the existing consumer. */
export function mergeMatchExperienceDelta(base, delta, verifiedBaseSha) {
  validateMatchExperienceDelta(delta);
  requireValue(verifiedBaseSha === MATCH_EXPERIENCE_BASE_SHA && delta.base_catalog_sha256 === verifiedBaseSha, 'base-sha');
  requireValue(base?.contract_version === delta.base_catalog_contract && base.view === 'STRICT_PUBLIC', 'base-contract');
  for (const match of delta.matches) {
    requireValue(match.participants.every((person) => person.athlete_id === null || base.stars.some((star) => star.athlete_id === person.athlete_id)), 'unregistered-athlete');
  }
  const merge = (rows, additions, key) => {
    requireValue(Array.isArray(rows), `base-${key}`);
    const result = [...rows];
    const incoming = new Set();
    for (const row of additions) {
      requireValue(!incoming.has(row[key]), `duplicate-${key}`);
      incoming.add(row[key]);
      const existing = result.find((old) => old[key] === row[key]);
      if (existing) requireValue(JSON.stringify(existing) === JSON.stringify(row), `conflict-${key}`);
      else result.push(row);
    }
    return result;
  };
  const candidate = { ...base,
    matches: merge(base.matches, delta.matches, 'match_id'),
    video_sources: merge(base.video_sources, delta.video_sources, 'source_id'),
    evidence_sources: merge(base.evidence_sources, delta.evidence_sources, 'source_id'),
  };
  candidate.quality_summary = { ...base.quality_summary,
    public_match_count: candidate.matches.length,
    public_video_source_count: candidate.video_sources.length,
    public_match_video_link_count: candidate.matches.filter((match) => match.match_video_link_status === 'HUMAN_VERIFIED').length,
  };
  const evidenceIds = new Set(candidate.evidence_sources.map((row) => row.source_id));
  for (const match of delta.matches) requireValue([...match.evidence_source_ids, ...match.rights.evidence_source_ids].every((id) => typeof id === 'string' && id.trim() && evidenceIds.has(id)), 'unregistered-match-evidence');
  // The existing consumer enforces exact bidirectional links and registered evidence.
  consumeFanCatalog(candidate);
  return candidate;
}

/** Apply after older deltas so their pinned baseline checks remain unchanged. */
export function applyMatchExperienceDelta(catalog, base, delta, verifiedBaseSha) {
  const projection = consumeFanCatalog(mergeMatchExperienceDelta(base, delta, verifiedBaseSha));
  for (const incoming of projection.sources.filter((row) => delta.video_sources.some((item) => item.source_id === row.source_id))) {
    requireValue(!catalog.sources.some((old) => old.source_id !== incoming.source_id && old.url === incoming.url), 'source-url-identity-conflict');
  }
  const append = (existing, ids, rows, key) => {
    const result = [...existing];
    for (const id of ids) {
      const row = rows.find((item) => item[key] === id);
      const old = result.find((item) => item[key] === id);
      if (old) requireValue(JSON.stringify(old) === JSON.stringify(row), `conflict-${key}`);
      else result.push(row);
    }
    return result;
  };
  const matches = append(catalog.matches, delta.matches.map((row) => row.match_id), projection.matches, 'match_id');
  const sources = append(catalog.sources, delta.video_sources.map((row) => row.source_id), projection.sources, 'source_id');
  const stars = catalog.stars.map((star) => ({ ...star, linked_matches: [...new Set([
    ...star.linked_matches,
    ...matches.filter((match) => match.participants.some((person) => person.athlete_id === star.athlete_id)).map((match) => match.match_id),
  ])] }));
  return { ...catalog, matches, sources, stars };
}
