// Local-only, transparent discovery profile. It records explicit open requests,
// not verified page views, and never duplicates SQLite favorites or media files.
export const PERSONAL_DISCOVERY_KEY = 'ptti.personal-discovery/0.1';
export const PERSONAL_DISCOVERY_VERSION = 'ptti.personal-discovery/0.1';

const MAX_RECENT = 50;
const MAX_LOCAL_PROGRESS = 100;
const VALID_RECORD_KINDS = new Set(['MatchIdentity', 'MediaSource', 'VideoAsset', 'Moment', 'Rally', 'PointEvent']);
const SHA256 = /^[a-f0-9]{64}$/i;
const onlyKeys = (value, keys) => Object.keys(value).every(key => keys.includes(key));

function fail(error) { return { ok: false, error }; }
function validText(value) { return typeof value === 'string' && value.trim().length > 0; }
function validDate(value) {
  return typeof value === 'string'
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)
    && Number.isFinite(Date.parse(value));
}
function validReference(ref) {
  return ref && typeof ref === 'object' && VALID_RECORD_KINDS.has(ref.record_kind) && validText(ref.record_id);
}
function validOpaqueId(value) { return validText(value) && !/[\\/]/.test(value) && !/^[a-z]:/i.test(value); }
function referenceKey(ref) { return `${ref.record_kind}:${ref.record_id}`; }

export function emptyPersonalDiscoveryProfile(profileId = 'local-default') {
  return {
    schema_version: PERSONAL_DISCOVERY_VERSION,
    profile_id: profileId,
    recently_opened: [],
    local_progress: [],
  };
}

export function validatePersonalDiscoveryProfile(profile) {
  if (!profile || typeof profile !== 'object' || Array.isArray(profile)
    || profile.schema_version !== PERSONAL_DISCOVERY_VERSION || !validOpaqueId(profile.profile_id)
    || !Array.isArray(profile.recently_opened) || !Array.isArray(profile.local_progress)
    || profile.recently_opened.length > MAX_RECENT || profile.local_progress.length > MAX_LOCAL_PROGRESS
    || !onlyKeys(profile, ['schema_version', 'profile_id', 'recently_opened', 'local_progress'])) return false;

  const recentKeys = new Set();
  for (const row of profile.recently_opened) {
    if (!validReference(row) || !validDate(row.open_requested_at)
      || !onlyKeys(row, ['record_kind', 'record_id', 'open_requested_at'])) return false;
    const key = referenceKey(row);
    if (recentKeys.has(key)) return false;
    recentKeys.add(key);
  }

  const progressKeys = new Set();
  for (const row of profile.local_progress) {
    if (!validOpaqueId(row.video_asset_id) || !SHA256.test(row.asset_sha256 ?? '')
      || !Number.isFinite(row.position_seconds) || row.position_seconds < 0
      || !Number.isFinite(row.duration_seconds) || row.duration_seconds <= 0
      || row.position_seconds > row.duration_seconds || !validDate(row.updated_at)
      || !validOpaqueId(row.rights_evidence_id) || row.asset_kind !== 'USER_LOCAL'
      || row.availability !== 'AVAILABLE' || row.identity_method !== 'VERIFIED_SHA256'
      || row.playback_rights !== 'USER_CONFIRMED'
      || !onlyKeys(row, ['video_asset_id', 'asset_sha256', 'position_seconds', 'duration_seconds', 'asset_kind', 'availability', 'identity_method', 'playback_rights', 'rights_evidence_id', 'updated_at'])) return false;
    const key = `${row.video_asset_id}:${row.asset_sha256.toLowerCase()}`;
    if (progressKeys.has(key)) return false;
    progressKeys.add(key);
  }
  return true;
}

// Reads never repair or write data. Malformed and newer-version bytes remain in
// storage and make the profile read-only until a separate explicit recovery flow.
export function readPersonalDiscovery(storage, key = PERSONAL_DISCOVERY_KEY) {
  if (!storage || typeof storage.getItem !== 'function') return { profile: null, exists: false, writable: false, error: 'STORAGE_UNAVAILABLE' };
  let raw;
  try { raw = storage.getItem(key); } catch { return { profile: null, exists: true, writable: false, error: 'READ_FAILED' }; }
  if (raw === null) return { profile: emptyPersonalDiscoveryProfile(), exists: false, writable: true, error: null };
  let profile;
  try { profile = JSON.parse(raw); } catch { return { profile: null, exists: true, writable: false, error: 'PROFILE_CORRUPT', preserved: true }; }
  if (profile?.schema_version !== PERSONAL_DISCOVERY_VERSION) return { profile: null, exists: true, writable: false, error: 'PROFILE_VERSION_UNSUPPORTED', preserved: true };
  if (!validatePersonalDiscoveryProfile(profile)) return { profile: null, exists: true, writable: false, error: 'PROFILE_INVALID', preserved: true };
  return { profile, exists: true, writable: true, error: null };
}

export function writePersonalDiscovery(storage, profile, key = PERSONAL_DISCOVERY_KEY) {
  if (!storage || typeof storage.getItem !== 'function' || typeof storage.setItem !== 'function') return fail('STORAGE_UNAVAILABLE');
  const current = readPersonalDiscovery(storage, key);
  if (!current.writable) return fail(current.error ?? 'STORAGE_UNAVAILABLE');
  if (!validatePersonalDiscoveryProfile(profile)) return fail('PROFILE_INVALID');
  try {
    const serialized = JSON.stringify(profile);
    storage.setItem(key, serialized);
    if (storage.getItem(key) !== serialized) return fail('WRITE_VERIFY_FAILED');
    return { ok: true, error: null, profile };
  } catch {
    return fail('WRITE_FAILED');
  }
}

export function recordOpenRequest(storage, reference, now = new Date().toISOString(), key = PERSONAL_DISCOVERY_KEY) {
  if (!validReference(reference) || !validDate(now)) return fail('OPEN_REFERENCE_INVALID');
  const current = readPersonalDiscovery(storage, key);
  if (!current.writable) return fail(current.error ?? 'STORAGE_UNAVAILABLE');
  const opened = { record_kind: reference.record_kind, record_id: reference.record_id, open_requested_at: now };
  const recentlyOpened = [opened, ...current.profile.recently_opened.filter(row => referenceKey(row) !== referenceKey(reference))].slice(0, MAX_RECENT);
  const result = writePersonalDiscovery(storage, { ...current.profile, recently_opened: recentlyOpened }, key);
  return result.ok ? { ...result, recorded: 'OPEN_REQUESTED' } : result;
}

export function saveTrustedLocalProgress(storage, input, now = new Date().toISOString(), key = PERSONAL_DISCOVERY_KEY) {
  const {
    videoAssetId, assetSha256, positionSeconds, durationSeconds,
    assetKind, availability, identityMethod, playbackRights, rightsEvidenceId,
  } = input ?? {};
  if (!validOpaqueId(videoAssetId) || !SHA256.test(assetSha256 ?? '') || assetKind !== 'USER_LOCAL'
    || availability !== 'AVAILABLE' || identityMethod !== 'VERIFIED_SHA256'
    || playbackRights !== 'USER_CONFIRMED' || !validOpaqueId(rightsEvidenceId)
    || !Number.isFinite(positionSeconds) || positionSeconds < 0
    || !Number.isFinite(durationSeconds) || durationSeconds <= 0
    || positionSeconds > durationSeconds || !validDate(now)) return fail('LOCAL_PROGRESS_NOT_TRUSTED');
  const current = readPersonalDiscovery(storage, key);
  if (!current.writable) return fail(current.error ?? 'STORAGE_UNAVAILABLE');
  const entry = {
    video_asset_id: videoAssetId,
    asset_sha256: assetSha256.toLowerCase(),
    position_seconds: positionSeconds,
    duration_seconds: durationSeconds,
    asset_kind: assetKind,
    availability,
    identity_method: identityMethod,
    playback_rights: playbackRights,
    rights_evidence_id: rightsEvidenceId,
    updated_at: now,
  };
  const id = `${videoAssetId}:${entry.asset_sha256}`;
  const localProgress = [entry, ...current.profile.local_progress.filter(row => `${row.video_asset_id}:${row.asset_sha256}` !== id)].slice(0, MAX_LOCAL_PROGRESS);
  const result = writePersonalDiscovery(storage, { ...current.profile, local_progress: localProgress }, key);
  return result.ok ? { ...result, recorded: 'LOCAL_PROGRESS' } : result;
}

// The SQLite favorite projection is passed in by the existing adapter and is
// returned as a view only; this module does not read, write, or duplicate it.
export function buildGrowthShelf({ profile, sqliteFavoriteRefs = [], curatedLists = [] } = {}) {
  const safeProfile = validatePersonalDiscoveryProfile(profile) ? profile : emptyPersonalDiscoveryProfile();
  return {
    recentlyOpened: safeProfile.recently_opened.map(row => ({ ...row, status: 'OPEN_REQUESTED' })),
    continueWatching: safeProfile.local_progress.filter(row => row.position_seconds < row.duration_seconds)
      .map(row => ({ ...row, status: 'USER_LOCAL_PROGRESS' })),
    favorites: Array.isArray(sqliteFavoriteRefs) ? sqliteFavoriteRefs.filter(validReference).map(row => ({ record_kind: row.record_kind, record_id: row.record_id })) : [],
    curatedLists: Array.isArray(curatedLists) ? curatedLists.map(list => ({ ...list })) : [],
  };
}

// Deterministic ranking is limited to a supplied catalog and exposes every
// reason. It never infers identity from labels, titles, athletes, or searches.
export function rankDiscoveryItems(items, { profile, sqliteFavoriteRefs = [], curatedRefs = [] } = {}) {
  if (!Array.isArray(items)) return [];
  const shelf = buildGrowthShelf({ profile, sqliteFavoriteRefs, curatedLists: [] });
  const recent = new Set(shelf.recentlyOpened.map(referenceKey));
  const favorites = new Set(shelf.favorites.map(referenceKey));
  const curated = new Set(Array.isArray(curatedRefs) ? curatedRefs.filter(validReference).map(referenceKey) : []);
  return items.map((item, index) => {
    const ref = { record_kind: item?.record_kind, record_id: item?.record_id };
    const reasons = [];
    let score = 0;
    if (validReference(ref) && recent.has(referenceKey(ref))) { score += 30; reasons.push('RECENTLY_OPENED'); }
    if (validReference(ref) && favorites.has(referenceKey(ref))) { score += 20; reasons.push('FAVORITED_IN_SQLITE'); }
    if (validReference(ref) && curated.has(referenceKey(ref))) { score += 10; reasons.push('CURATOR_SELECTED'); }
    return { item, score, reasons, ranking: 'EXPLICIT_RULES_V0_1', _order: index };
  }).sort((a, b) => b.score - a.score || a._order - b._order)
    .map(({ _order, ...ranked }) => ranked);
}
