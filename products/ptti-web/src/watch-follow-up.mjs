export const USER_WATCH_PLAYBACK_REPORTS_SHA256 = 'd24da470141984fcd0841daf109d3bed6a449fdc6f4df889aac2172a555de3f0';

function fail(code) {
  throw new Error(code);
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

/** Join user-supplied reports by the exact source ID and official URL only. */
export function indexUserReportedPlaybackEvidence(envelope, catalogSources) {
  if (!isObject(envelope) || envelope.contract_version !== 'ptti.user-watch-playback-reports/0.1'
    || envelope.evidence_class !== 'USER_REPORTED' || !/^\d{4}-\d{2}-\d{2}$/.test(envelope.recorded_on)
    || !Array.isArray(envelope.reports) || envelope.reports.length !== 3
    || !Array.isArray(catalogSources)) fail('invalid-user-playback-report-envelope');
  const catalogById = new Map();
  for (const source of catalogSources) {
    if (!source || typeof source.source_id !== 'string' || typeof source.url !== 'string' || catalogById.has(source.source_id)) fail('invalid-user-playback-report-catalog');
    catalogById.set(source.source_id, source);
  }
  const joined = new Map();
  for (const report of envelope.reports) {
    if (!isObject(report) || typeof report.report_id !== 'string' || !report.report_id
      || typeof report.source_id !== 'string' || !report.source_id
      || typeof report.official_target_url !== 'string'
      || report.evidence_type !== 'USER_REPORTED' || report.conclusion !== 'STARTED_PLAYBACK'
      || report.feedback_source !== 'USER_PROVIDED_IN_REQUEST' || report.tested_at !== null) fail('invalid-user-playback-report');
    if (joined.has(report.source_id) || [...joined.values()].some((row) => row.report_id === report.report_id)) fail('duplicate-user-playback-report');
    const source = catalogById.get(report.source_id);
    if (!source) fail(`user-playback-source-id-mismatch:${report.source_id}`);
    if (source.url !== report.official_target_url) fail(`user-playback-source-url-mismatch:${report.source_id}`);
    joined.set(report.source_id, { ...report, recorded_on: envelope.recorded_on });
  }
  if (joined.size !== 3) fail('invalid-user-playback-report-count');
  return joined;
}

/** Add browser-local user reports only when their ID and URL both match the public source catalog. */
export function mergeLocalUserFeedbackSources(reportedBySourceId, catalogSources, localReports) {
  if (!(reportedBySourceId instanceof Map) || !Array.isArray(catalogSources) || !Array.isArray(localReports)) fail('invalid-local-watch-feedback-input');
  const catalogById = new Map(catalogSources.map((source) => [source.source_id, source]));
  const merged = new Map(reportedBySourceId);
  for (const report of localReports) {
    if (!report || report.evidence_class !== 'USER_REPORTED' || typeof report.source_id !== 'string' || typeof report.source_url !== 'string') fail('invalid-local-watch-feedback-row');
    const source = catalogById.get(report.source_id);
    if (!source) fail(`local-watch-feedback-source-id-mismatch:${report.source_id}`);
    if (source.url !== report.source_url) fail(`local-watch-feedback-source-url-mismatch:${report.source_id}`);
    merged.set(report.source_id, report);
  }
  return merged;
}

/** Build a manual-review queue from catalog/evidence, excluding only exact reported sources. */
export function buildWatchFollowUpQueue(catalogSources, evidenceBySourceId, reportedBySourceId) {
  if (!Array.isArray(catalogSources) || !(evidenceBySourceId instanceof Map) || !(reportedBySourceId instanceof Map)) fail('invalid-watch-follow-up-input');
  const queue = [];
  for (const source of catalogSources) {
    if (reportedBySourceId.has(source.source_id)) continue;
    const evidence = evidenceBySourceId.get(source.source_id);
    if (!evidence || evidence.official_target_url !== source.url || (evidence.match_id ?? null) !== (source.canonical_match_id ?? null)) fail(`watch-follow-up-evidence-mismatch:${source.source_id}`);
    let priority;
    let priorityKey;
    if (source.match_link_status === 'HUMAN_VERIFIED' && source.canonical_match_id) {
      priority = 1;
      priorityKey = 'watchEvidence.priorityMatchVerified';
    } else if (source.match_link_status === 'OFFICIAL_TITLE_ASSOCIATED_VISUAL_NOT_TESTED' && source.canonical_match_id) {
      priority = 2;
      priorityKey = 'watchEvidence.priorityTitleOnly';
    } else if (!source.canonical_match_id && evidence.video_type_claim === 'EVENT_HIGHLIGHTS_TITLE_CLAIM') {
      priority = 3;
      priorityKey = 'watchEvidence.priorityEventHighlights';
    } else {
      priority = 4;
      priorityKey = 'watchEvidence.priorityOther';
    }
    queue.push({ source, evidence, priority, priorityKey });
  }
  return queue.sort((left, right) => left.priority - right.priority || left.source.source_id.localeCompare(right.source.source_id));
}
