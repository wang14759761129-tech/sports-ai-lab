export const GOAL19_WATCHABILITY_SHA256 = '8ba35a9575d2c731a55262c5edf7b8ea7477319f2d1fd7160c36de6ff09ff2f5';

function fail(code) {
  throw new Error(code);
}

export function createWatchabilityEvidenceIndex(evidence, catalogSources) {
  if (!evidence || evidence.contract_version !== 'ptti.goal19.1-watchability-evidence/0.1'
    || evidence.audience !== 'SAN_INTERNAL_REVIEW_ADDENDUM' || evidence.additive_only !== true) fail('goal19-invalid-envelope');
  if (!Array.isArray(evidence.sources) || evidence.sources.length !== 17
    || evidence.summary?.source_count !== 17 || evidence.summary?.unique_source_id_count !== 17
    || evidence.summary?.unique_target_url_count !== 17) fail('goal19-invalid-counts');
  if (!Array.isArray(catalogSources) || catalogSources.length !== 17) fail('goal19-catalog-source-count-mismatch');

  const rowsById = new Map();
  const evidenceUrls = new Set();
  for (const row of evidence.sources) {
    if (!row || typeof row.source_id !== 'string' || !row.source_id || typeof row.official_target_url !== 'string') fail('goal19-invalid-source-row');
    if (rowsById.has(row.source_id)) fail('goal19-duplicate-source-id');
    if (evidenceUrls.has(row.official_target_url)) fail('goal19-duplicate-target-url');
    rowsById.set(row.source_id, row);
    evidenceUrls.add(row.official_target_url);
  }

  const catalogById = new Map();
  for (const source of catalogSources) {
    if (!source || typeof source.source_id !== 'string' || !source.source_id || typeof source.url !== 'string') fail('goal19-invalid-catalog-source');
    if (catalogById.has(source.source_id)) fail('goal19-duplicate-catalog-source-id');
    catalogById.set(source.source_id, source);
  }
  if (catalogById.size !== rowsById.size || [...rowsById.keys()].some((id) => !catalogById.has(id))) fail('goal19-source-id-set-mismatch');

  const joined = new Map();
  for (const [sourceId, row] of rowsById) {
    const source = catalogById.get(sourceId);
    if (row.official_target_url !== source.url) fail(`goal19-target-url-mismatch:${sourceId}`);
    if ((row.match_id ?? null) !== (source.canonical_match_id ?? null)) fail(`goal19-match-identity-mismatch:${sourceId}`);
    joined.set(sourceId, row);
  }

  const baseline = evidence.summary.match_link_baseline_counts;
  if (baseline?.HUMAN_VERIFIED !== 5 || baseline?.UNKNOWN !== 10
    || baseline?.['OFFICIAL_VIDEO_TITLE_MATCH_ASSOCIATION; VISUAL_MATCH_NOT_TESTED'] !== 2
    || evidence.summary.source_match_link_count !== 7 || evidence.summary.event_level_or_unlinked_count !== 10) fail('goal19-link-baseline-mismatch');
  if (evidence.summary.external_system_browser_open_count !== 0
    || evidence.summary.direct_video_start_count !== 0 || evidence.summary.complete_watch_count !== 0) fail('goal19-playback-level-promotion');
  return joined;
}
