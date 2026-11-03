export const FAN_LOCAL_DATA_VERSION = 'ptti.fan-local-data/2';
export const LEGACY_FAN_LOCAL_DATA_VERSION = 'ptti.fan-local-data/1';
export const FAN_LOCAL_DATA_KEY = 'ptti-fan-universe-local-v1';
const MAX_BACKUP_CHARS = 1_000_000;

export function emptyFanLocalData() {
  return { contract_version: FAN_LOCAL_DATA_VERSION, saved_match_ids: [], followed_athlete_ids: [], training_notes: [], match_notes: [], coach_notes: [], fan_notes: [] };
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function validString(value, max = 2000) {
  return typeof value === 'string' && value.length <= max;
}

function validDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function validateNotes(value, code) {
  if (!Array.isArray(value)) throw new Error(code);
  const ids = new Set();
  for (const note of value) {
    if (!isObject(note)
      || typeof note.id !== 'string' || !note.id || ids.has(note.id)
      || !validDate(note.date)
      || !validString(note.topic, 120) || !note.topic.trim()
      || !validString(note.technical_question, 1000)
      || !validString(note.summary, 2000)
      || !validString(note.next_goal, 1000)
      || !(note.match_id === null || (typeof note.match_id === 'string' && note.match_id.length <= 200))) {
      throw new Error(code);
    }
    ids.add(note.id);
  }
}

export function consumeFanLocalData(value) {
  if (!isObject(value) || ![FAN_LOCAL_DATA_VERSION, LEGACY_FAN_LOCAL_DATA_VERSION].includes(value.contract_version)) throw new Error('unsupported-fan-local-data-version');
  const legacy = value.contract_version === LEGACY_FAN_LOCAL_DATA_VERSION;
  for (const key of ['saved_match_ids', 'followed_athlete_ids']) {
    if (!Array.isArray(value[key]) || value[key].some((id) => typeof id !== 'string' || !id)
      || new Set(value[key]).size !== value[key].length) throw new Error(`invalid-${key}`);
  }
  const noteCollections = legacy
    ? [['training_notes', 'invalid-training-notes'], ['fan_notes', 'invalid-fan-notes']]
    : [['training_notes', 'invalid-training-notes'], ['match_notes', 'invalid-match-notes'], ['coach_notes', 'invalid-coach-notes'], ['fan_notes', 'invalid-fan-notes']];
  for (const [key, code] of noteCollections) validateNotes(value[key], code);
  return {
    contract_version: FAN_LOCAL_DATA_VERSION,
    saved_match_ids: [...value.saved_match_ids],
    followed_athlete_ids: [...value.followed_athlete_ids],
    training_notes: value.training_notes.map((note) => ({ ...note })),
    match_notes: legacy ? [] : value.match_notes.map((note) => ({ ...note })),
    coach_notes: legacy ? [] : value.coach_notes.map((note) => ({ ...note })),
    fan_notes: value.fan_notes.map((note) => ({ ...note })),
  };
}

export function readFanLocalData(storage) {
  const raw = storage.getItem(FAN_LOCAL_DATA_KEY);
  if (raw === null) return emptyFanLocalData();
  return consumeFanLocalData(JSON.parse(raw));
}

export function writeFanLocalData(storage, value) {
  const accepted = consumeFanLocalData(value);
  storage.setItem(FAN_LOCAL_DATA_KEY, JSON.stringify(accepted));
  return accepted;
}

export function parseFanLocalDataBackup(text) {
  if (typeof text !== 'string' || text.length > MAX_BACKUP_CHARS) throw new Error('fan-local-backup-too-large');
  let parsed;
  try { parsed = JSON.parse(text); } catch { throw new Error('invalid-fan-local-backup-json'); }
  return consumeFanLocalData(parsed);
}

export function validateFanLocalDataReferences(value, { matchIds, athleteIds }) {
  const data = consumeFanLocalData(value);
  const matches = new Set(matchIds);
  const athletes = new Set(athleteIds);
  if (data.saved_match_ids.some((id) => !matches.has(id))
    || data.followed_athlete_ids.some((id) => !athletes.has(id))
    || [...data.training_notes, ...data.match_notes, ...data.coach_notes, ...data.fan_notes]
      .some((note) => note.match_id !== null && !matches.has(note.match_id))) {
    throw new Error('backup-reference-not-in-public-catalog');
  }
  return data;
}

export function serializeFanLocalDataBackup(value) {
  return JSON.stringify(consumeFanLocalData(value), null, 2);
}

export function toggleLocalId(values, id) {
  if (typeof id !== 'string' || !id) throw new Error('local-id-required');
  return values.includes(id) ? values.filter((value) => value !== id) : [...values, id];
}
