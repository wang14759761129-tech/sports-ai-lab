import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(SCRIPT_DIR, '../../..');
const BASE_PATH = resolve(REPO_ROOT, 'products/ptti-integration/generated/goal15-main-fan-universe-public-v0.2/match-library-strict-public.json');
const DELTA_PATH = resolve(REPO_ROOT, 'products/ptti-integration/generated/goal17-1-real-content-v0.1/public/official-match-video-additions.json');
const OUT_PATH = resolve(REPO_ROOT, 'products/ptti-integration/generated/goal19-1-watchability-evidence-v0.1/watchability-evidence-v0.1.json');
const BASE_SHA256 = '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930';
const DELTA_SHA256 = '6f05d1fc48fb74ffc305abe20fd9152973bd96bb009fe6a183d42c031a31198a';

// Direct read-only web retrieval outcomes from 2026-10-19. These are not
// external-system-browser launches or playback observations.
const CURRENT_FETCH_OBSERVATIONS = new Map([
  ['video-source:youtube:0QgbtsBWZhk', {
    result: 'PAGE_TITLE_SURFACED',
    observed_title: "FULL MATCH | Wang Chuqin vs Felix Lebrun | MS Final | #ChinaSmash 2025",
    note: 'The research fetch surfaced the expected YouTube title. No player frames or playback were observed.'
  }],
  ['video-source:youtube:ttUevnAZSEY', {
    result: 'BLOCKED_FETCH_THROTTLED',
    observed_title: null,
    note: 'The read-only page fetch returned an online-fetch throttling response; no alternate access route was attempted.'
  }],
  ['video-source:youtube:cDccQqVlMnc', {
    result: 'BLOCKED_FETCH_THROTTLED',
    observed_title: null,
    note: 'The read-only page fetch returned an online-fetch throttling response; no alternate access route was attempted.'
  }],
  ['youtube:ywX9mUJ8NtI', {
    result: 'BLOCKED_FETCH_THROTTLED',
    observed_title: null,
    note: 'The read-only page fetch returned an online-fetch throttling response; no alternate access route was attempted.'
  }],
  ['youtube:Kbhf47vb3eE', {
    result: 'BLOCKED_FETCH_THROTTLED',
    observed_title: null,
    note: 'The read-only page fetch returned an online-fetch throttling response; no alternate access route was attempted.'
  }]
]);
const EVENT_PAGE_OBSERVATIONS = [
  {
    event_id: '3231',
    url: 'https://www.worldtabletennis.com/eventInfo?eventId=3231',
    checked_on: '2026-10-19',
    method: 'READ_ONLY_WEB_PAGE_FETCH',
    status: 'PAGE_SHELL_ONLY_CONTENT_NOT_EXPOSED',
    note: 'The response exposed a cookie-consent/iframe shell only; no draw, result, participant or event-date facts were independently rechecked.'
  },
  {
    event_id: '3098',
    url: 'https://www.worldtabletennis.com/eventInfo?eventId=3098',
    checked_on: '2026-10-19',
    method: 'READ_ONLY_WEB_PAGE_FETCH',
    status: 'PAGE_SHELL_ONLY_CONTENT_NOT_EXPOSED',
    note: 'The response exposed a cookie-consent/iframe shell only; no draw, result, participant or event-date facts were independently rechecked.'
  }
];

function sha256(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function readJson(filePath) {
  return readFile(filePath).then((bytes) => ({ bytes, json: JSON.parse(bytes.toString('utf8')) }));
}

function safePermission(value, fallback = 'UNKNOWN') {
  return typeof value === 'string' && value.length > 0 ? value : fallback;
}

function sourceFields(source, matchById) {
  const availability = source.availability ?? {};
  const rights = source.rights ?? {};
  const observation = CURRENT_FETCH_OBSERVATIONS.get(source.source_id) ?? {
    result: 'NOT_TESTED_THIS_SPRINT',
    observed_title: null,
    note: 'No current page fetch was attempted for this source in this sprint.'
  };
  const rawType = source.content_type_claim ?? source.content_type ?? null;
  const titleClaim = typeof source.title === 'string' && /\bFULL MATCH\b/i.test(source.title)
    ? 'FULL_MATCH_TITLE_CLAIM'
    : null;
  const linkedMatchId = source.canonical_match_id ?? source.match_id ?? null;
  const linkedMatch = linkedMatchId ? matchById.get(linkedMatchId) : null;
  const videoTypeClaim = rawType === 'FULL_MATCH'
    ? 'FULL_MATCH_TITLE_CLAIM'
    : rawType === 'HIGHLIGHTS'
      ? 'EVENT_HIGHLIGHTS_TITLE_CLAIM'
      : titleClaim ?? (source.match_id || source.canonical_match_id ? 'MATCH_SPECIFIC_TYPE_UNKNOWN' : 'EVENT_LEVEL_OR_UNLINKED_TYPE_UNKNOWN');

  return {
    source_id: source.source_id,
    match_id: linkedMatchId,
    official_target_url: source.official_url ?? source.watch_url,
    publisher: source.publisher ?? null,
    publisher_identity_baseline: source.publisher_identity_status ?? source.publisher_status ?? 'UNKNOWN',
    source_identity_baseline: source.source_identity_status ?? 'UNKNOWN',
    match_link_baseline: source.match_link_status ?? source.identity_status ?? linkedMatch?.identity_status ?? 'UNKNOWN',
    video_type_claim: videoTypeClaim,
    video_type_evidence: rawType ? 'BASE_PACKAGE_TITLE_METADATA_CLAIM' : titleClaim ? 'TITLE_TEXT_ONLY' : 'UNKNOWN',
    claimed_full_match_completeness: source.completeness_status ?? 'UNVERIFIED',
    current_page_fetch: {
      checked_on: '2026-10-19',
      method: 'READ_ONLY_WEB_PAGE_FETCH',
      status: observation.result,
      observed_title: observation.observed_title,
      note: observation.note
    },
    verification_levels: {
      page_exists: observation.result === 'PAGE_TITLE_SURFACED' ? 'PARTIAL_PAGE_TITLE_SURFACED' : observation.result === 'BLOCKED_FETCH_THROTTLED' ? 'BLOCKED' : 'NOT_TESTED',
      official_target_correct: observation.result === 'PAGE_TITLE_SURFACED' ? 'PARTIAL_TITLE_MATCH_WITH_BASELINE_VERIFIED_PUBLISHER' : 'NOT_RECONFIRMED_THIS_SPRINT',
      external_system_browser_open: 'NOT_TESTED',
      video_started: 'NOT_TESTED',
      complete_watch: 'UNVERIFIED'
    },
    access: {
      territory: safePermission(availability.territory_availability ?? source.territory_status, 'UNKNOWN'),
      login_or_paywall: safePermission(availability.login_or_paywall ?? source.login_status, 'UNKNOWN_OR_NOT_TESTED'),
      latest_playback_status: safePermission(availability.latest_recorded_playback_status ?? source.playback_status, 'NOT_TESTED'),
      historical_embed_status: safePermission(availability.platform_embed?.latest_recorded_technical_status, 'NOT_TESTED'),
      current_embed_permission: safePermission(rights.embedding ?? source.embed_permission, 'UNKNOWN'),
      thumbnail_display_permission: safePermission(rights.thumbnail_display ?? source.thumbnail_display_permission, 'UNKNOWN'),
      download_permission: safePermission(rights.download ?? source.download_permission, 'UNKNOWN'),
      local_analysis_permission: safePermission(rights.local_analysis ?? source.local_analysis_permission, 'UNKNOWN'),
      redistribution_permission: safePermission(rights.redistribution ?? source.redistribution_permission, 'UNKNOWN'),
      external_watch_route: source.watch_entry ?? source.watch_route ?? 'OPEN_OFFICIAL_PLATFORM_URL',
      external_viewing_permission: safePermission(rights.external_viewing, 'UNKNOWN')
    },
    source_recorded_at: source.source_verified_at ?? source.source_published_at ?? null
  };
}

export function buildEvidenceReport({ base, baseBytes, delta, deltaBytes, generatedAt = new Date().toISOString() }) {
  const baseSources = base.video_sources ?? [];
  const deltaSources = delta.video_sources ?? [];
  const matchById = new Map([...(base.matches ?? []), ...(delta.matches ?? [])].map((match) => [match.match_id, match]));
  const sources = [...baseSources, ...deltaSources].map((source) => sourceFields(source, matchById));
  const ids = sources.map((source) => source.source_id);
  const urls = sources.map((source) => source.official_target_url);
  const mapped = sources.filter((source) => source.match_id !== null).length;
  const currentResults = [...CURRENT_FETCH_OBSERVATIONS.values()];
  const countBy = (items, keyFn) => Object.fromEntries([...new Set(items.map(keyFn))].map((key) => [key, items.filter((item) => keyFn(item) === key).length]));
  return {
    contract_version: 'ptti.goal19.1-watchability-evidence/0.1',
    generated_at: generatedAt,
    audience: 'SAN_INTERNAL_REVIEW_ADDENDUM',
    additive_only: true,
    input_identity: {
      base_contract: base.contract_version,
      base_sha256: sha256(baseBytes),
      goal17_1_delta_contract: delta.contract_version,
      goal17_1_delta_sha256: sha256(deltaBytes)
    },
    summary: {
      source_count: sources.length,
      unique_source_id_count: new Set(ids).size,
      unique_target_url_count: new Set(urls).size,
      source_match_link_count: mapped,
      event_level_or_unlinked_count: sources.length - mapped,
      current_fetch_title_surfaced_count: currentResults.filter((item) => item.result === 'PAGE_TITLE_SURFACED').length,
      current_fetch_throttled_count: currentResults.filter((item) => item.result === 'BLOCKED_FETCH_THROTTLED').length,
      current_fetch_not_attempted_count: sources.length - CURRENT_FETCH_OBSERVATIONS.size,
      video_type_claim_counts: countBy(sources, (source) => source.video_type_claim),
      match_link_baseline_counts: countBy(sources, (source) => source.match_link_baseline),
      external_system_browser_open_count: 0,
      direct_video_start_count: 0,
      complete_watch_count: 0
    },
    verification_definitions: {
      page_exists: 'Evidence that page content was retrieved; a title surface is partial evidence only.',
      official_target_correct: 'Exact title/URL agreement and previously recorded publisher identity; does not imply playback.',
      external_system_browser_open: 'Must be tested in the user operating system browser; research fetch is not this test.',
      video_started: 'Requires observed moving video frames or equivalent direct playback evidence.',
      complete_watch: 'Requires evidence covering the full video; title claims are insufficient.'
    },
    supplemental_event_page_fetches: EVENT_PAGE_OBSERVATIONS,
    sources
  };
}

export function validateEvidenceReport(report) {
  const errors = [];
  if (report.contract_version !== 'ptti.goal19.1-watchability-evidence/0.1') errors.push('wrong_contract_version');
  if (report.audience !== 'SAN_INTERNAL_REVIEW_ADDENDUM' || report.additive_only !== true) errors.push('unsafe_audience_or_mutability');
  if (!Array.isArray(report.sources) || report.sources.length !== 17) errors.push('source_count_must_be_17');
  const ids = report.sources?.map((source) => source.source_id) ?? [];
  const urls = report.sources?.map((source) => source.official_target_url) ?? [];
  if (new Set(ids).size !== ids.length) errors.push('duplicate_source_id');
  if (new Set(urls).size !== urls.length) errors.push('duplicate_target_url');
  const mappedCount = (report.sources ?? []).filter((source) => source.match_id !== null).length;
  if (report.summary?.source_count !== report.sources?.length) errors.push('summary_source_count_mismatch');
  if (report.summary?.unique_source_id_count !== new Set(ids).size) errors.push('summary_source_id_count_mismatch');
  if (report.summary?.unique_target_url_count !== new Set(urls).size) errors.push('summary_target_url_count_mismatch');
  if (report.summary?.source_match_link_count !== mappedCount) errors.push('summary_match_link_count_mismatch');
  if (report.summary?.event_level_or_unlinked_count !== (report.sources?.length ?? 0) - mappedCount) errors.push('summary_unlinked_count_mismatch');
  for (const source of report.sources ?? []) {
    if (!source.source_id || !/^https:\/\/www\.youtube\.com\/watch\?v=[A-Za-z0-9_-]+$/.test(source.official_target_url ?? '')) errors.push(`invalid_source_or_url:${source.source_id ?? 'missing'}`);
    if (source.verification_levels?.external_system_browser_open !== 'NOT_TESTED') errors.push(`external_browser_evidence_escalated:${source.source_id}`);
    if (source.verification_levels?.video_started !== 'NOT_TESTED') errors.push(`playback_evidence_escalated:${source.source_id}`);
    if (source.verification_levels?.complete_watch !== 'UNVERIFIED') errors.push(`completeness_evidence_escalated:${source.source_id}`);
    if (source.video_type_claim === 'EVENT_HIGHLIGHTS_TITLE_CLAIM' && source.match_id !== null) errors.push(`event_highlights_bound_to_match:${source.source_id}`);
    const access = source.access ?? {};
    if (access.current_embed_permission === 'ALLOWED' || access.thumbnail_display_permission === 'ALLOWED' || access.download_permission === 'ALLOWED' || access.local_analysis_permission === 'ALLOWED' || access.redistribution_permission === 'ALLOWED') errors.push(`rights_escalated:${source.source_id}`);
  }
  if (report.summary?.direct_video_start_count !== 0 || report.summary?.complete_watch_count !== 0) errors.push('summary_playback_count_escalated');
  return { valid: errors.length === 0, errors };
}

async function main() {
  const args = new Set(process.argv.slice(2));
  const [{ bytes: baseBytes, json: base }, { bytes: deltaBytes, json: delta }] = await Promise.all([readJson(BASE_PATH), readJson(DELTA_PATH)]);
  if (sha256(baseBytes) !== BASE_SHA256 || sha256(deltaBytes) !== DELTA_SHA256) throw new Error('locked_input_sha_mismatch');
  const freshlyBuilt = buildEvidenceReport({ base, baseBytes, delta, deltaBytes });
  let report = freshlyBuilt;
  if (args.has('--validate')) {
    try {
      report = JSON.parse(await readFile(OUT_PATH, 'utf8'));
    } catch (error) {
      throw new Error(`generated_artifact_unavailable:${error.code ?? error.message}`);
    }
    if (JSON.stringify(report.input_identity) !== JSON.stringify(freshlyBuilt.input_identity)) throw new Error('generated_artifact_input_identity_mismatch');
    if (JSON.stringify({ ...report, generated_at: freshlyBuilt.generated_at }) !== JSON.stringify(freshlyBuilt)) throw new Error('generated_artifact_content_mismatch');
  }
  const validation = validateEvidenceReport(report);
  if (!validation.valid) throw new Error(`validation_failed:${validation.errors.join(',')}`);
  if (args.has('--build')) {
    await mkdir(dirname(OUT_PATH), { recursive: true });
    await writeFile(OUT_PATH, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  }
  if (!args.has('--build') && !args.has('--validate')) {
    throw new Error('usage: node build_goal19_1_watchability_evidence.mjs --build|--validate');
  }
  console.log(JSON.stringify({ status: 'PASS', mode: args.has('--build') ? 'build' : 'validate', ...report.summary, input_identity: report.input_identity }, null, 2));
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch((error) => { console.error(error.message); process.exitCode = 1; });
}
