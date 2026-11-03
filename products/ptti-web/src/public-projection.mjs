const internalManifestPath = /(?:internal-review|candidate-review|fixtures\/|scripts\/build_|goal1[14]-)/i;
const internalAuditKey = /^(?:goal11_internal_|goal14_(?:highlight_candidate_review|candidate_|highlight_links_admitted)|goal15_new_)/i;

export function inspectPublicProjection(catalog, rawText = JSON.stringify(catalog)) {
  const issues = [];
  if (catalog?.contract_version !== 'ptti.match-library-index/0.1') issues.push('unsupported contract version');
  if (catalog?.view !== 'STRICT_PUBLIC') issues.push('view is not STRICT_PUBLIC');
  if (catalog?.source_manifest != null && !Array.isArray(catalog.source_manifest)) issues.push('source_manifest is not an array');
  for (const entry of Array.isArray(catalog?.source_manifest) ? catalog.source_manifest : []) {
    if (typeof entry?.file === 'string' && internalManifestPath.test(entry.file)) issues.push(`internal source_manifest path: ${entry.file}`);
  }
  if (catalog?.quality_summary != null && (typeof catalog.quality_summary !== 'object' || Array.isArray(catalog.quality_summary))) issues.push('quality_summary is not an object');
  for (const key of Object.keys(catalog?.quality_summary && typeof catalog.quality_summary === 'object' && !Array.isArray(catalog.quality_summary) ? catalog.quality_summary : {})) {
    if (internalAuditKey.test(key)) issues.push(`internal review/build metric: ${key}`);
  }
  if (typeof rawText !== 'string' || /(?:^|["'\s])[A-Za-z]:[\\/]/m.test(rawText)) issues.push('absolute Windows path present');
  return issues;
}
