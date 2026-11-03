export const USER_WATCH_FEEDBACK_VERSION = 'ptti.user-watch-feedback/0.1';
export const USER_WATCH_FEEDBACK_KEY = 'ptti-user-watch-feedback-v0.1';
export const USER_REPORTED = 'USER_REPORTED';

const playbackStartedValues = new Set(['YES', 'NO', 'UNSURE']);
const binaryUnknownValues = new Set(['YES', 'NO', 'UNKNOWN']);

function fail(code) {
  throw new Error(code);
}

function validIso(value) {
  return typeof value === 'string' && Number.isFinite(Date.parse(value)) && value.includes('T');
}

export function validateUserWatchFeedbackReport(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || value.evidence_class !== USER_REPORTED
    || typeof value.report_id !== 'string' || !value.report_id
    || typeof value.source_id !== 'string' || !value.source_id
    || typeof value.source_url !== 'string'
    || typeof value.tested_at !== 'string' || !validIso(value.tested_at)
    || !playbackStartedValues.has(value.playback_started)
    || !binaryUnknownValues.has(value.login_required)
    || !binaryUnknownValues.has(value.territory_restricted)) fail('invalid-user-watch-feedback-report');
  let url;
  try { url = new URL(value.source_url); } catch { fail('invalid-user-watch-feedback-url'); }
  if (url.protocol !== 'https:') fail('invalid-user-watch-feedback-url');
  return {
    evidence_class: USER_REPORTED,
    report_id: value.report_id,
    source_id: value.source_id,
    source_url: value.source_url,
    tested_at: value.tested_at,
    playback_started: value.playback_started,
    login_required: value.login_required,
    territory_restricted: value.territory_restricted,
  };
}

export function createUserWatchFeedbackReport({ reportId, source, testedAt, playbackStarted, loginRequired, territoryRestricted }) {
  return validateUserWatchFeedbackReport({
    evidence_class: USER_REPORTED,
    report_id: reportId,
    source_id: source?.source_id,
    source_url: source?.url,
    tested_at: testedAt,
    playback_started: playbackStarted,
    login_required: loginRequired,
    territory_restricted: territoryRestricted,
  });
}

export function readUserWatchFeedback(storage) {
  const raw = storage.getItem(USER_WATCH_FEEDBACK_KEY);
  if (raw === null) return [];
  let parsed;
  try { parsed = JSON.parse(raw); } catch { fail('invalid-user-watch-feedback-json'); }
  if (!Array.isArray(parsed)) fail('invalid-user-watch-feedback-list');
  const reports = parsed.map(validateUserWatchFeedbackReport);
  if (new Set(reports.map((report) => report.report_id)).size !== reports.length) fail('duplicate-user-watch-feedback-id');
  return reports;
}

export function appendUserWatchFeedback(storage, report) {
  const accepted = validateUserWatchFeedbackReport(report);
  const reports = readUserWatchFeedback(storage);
  if (reports.some((row) => row.report_id === accepted.report_id)) fail('duplicate-user-watch-feedback-id');
  reports.push(accepted);
  storage.setItem(USER_WATCH_FEEDBACK_KEY, JSON.stringify(reports));
  return reports;
}

export function serializeUserWatchFeedback(reports) {
  const accepted = reports.map(validateUserWatchFeedbackReport);
  if (new Set(accepted.map((report) => report.report_id)).size !== accepted.length) fail('duplicate-user-watch-feedback-id');
  return JSON.stringify({
    contract_version: USER_WATCH_FEEDBACK_VERSION,
    evidence_class: USER_REPORTED,
    reports: accepted,
  }, null, 2);
}

export function parseUserWatchFeedbackExport(text) {
  let parsed;
  try { parsed = JSON.parse(text); } catch { fail('invalid-user-watch-feedback-export-json'); }
  if (!parsed || parsed.contract_version !== USER_WATCH_FEEDBACK_VERSION || parsed.evidence_class !== USER_REPORTED || !Array.isArray(parsed.reports)) fail('invalid-user-watch-feedback-export');
  const reports = parsed.reports.map(validateUserWatchFeedbackReport);
  if (new Set(reports.map((report) => report.report_id)).size !== reports.length) fail('duplicate-user-watch-feedback-id');
  return { contract_version: USER_WATCH_FEEDBACK_VERSION, evidence_class: USER_REPORTED, reports };
}
