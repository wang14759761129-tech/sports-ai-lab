export const FAN_LOCAL_DATA_VERSION = 'ptti.fan-local-data/2';
export const LEGACY_FAN_LOCAL_DATA_VERSION = 'ptti.fan-local-data/1';
export const FAN_LOCAL_DATA_KEY = 'ptti-fan-universe-local-v1';
export const FAN_LOCAL_RECOVERY_KEY = 'ptti-fan-local-import-recovery-v1';
const MAX_BACKUP_CHARS = 1_000_000;
export const ATHLETE_JOURNAL_FIELDS = ['training_goal', 'serve_receive', 'technical_issue', 'key_point_mindset', 'coach_observation', 'next_improvement'];

export function consumeAthleteJournal(value) {
  if (!isObject(value) || value.contract_version !== 'ptti.athlete-journal/0.1' || value.author !== 'SELF'
    || Object.keys(value).some((key) => !['contract_version', 'author', ...ATHLETE_JOURNAL_FIELDS].includes(key))
    || ATHLETE_JOURNAL_FIELDS.some((key) => !validString(value[key], 1000))) throw new Error('invalid-athlete-journal');
  return Object.fromEntries(['contract_version', 'author', ...ATHLETE_JOURNAL_FIELDS].map((key) => [key, value[key]]));
}

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
      || Object.keys(note).some((key) => !['id', 'date', 'topic', 'technical_question', 'summary', 'next_goal', 'match_id', 'athlete_journal'].includes(key))
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
    if (note.athlete_journal !== undefined) consumeAthleteJournal(note.athlete_journal);
  }
}

export function consumeFanLocalData(value) {
  if (!isObject(value) || ![FAN_LOCAL_DATA_VERSION, LEGACY_FAN_LOCAL_DATA_VERSION].includes(value.contract_version)) throw new Error('unsupported-fan-local-data-version');
  const legacy = value.contract_version === LEGACY_FAN_LOCAL_DATA_VERSION;
  const keys = ['contract_version', 'saved_match_ids', 'followed_athlete_ids', 'training_notes', 'fan_notes', ...(legacy ? [] : ['match_notes', 'coach_notes'])];
  if (Object.keys(value).some((key) => !keys.includes(key))) throw new Error('unknown-fan-local-data-field');
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
    training_notes: value.training_notes.map((note) => ({ ...note, ...(note.athlete_journal ? { athlete_journal: consumeAthleteJournal(note.athlete_journal) } : {}) })),
    match_notes: legacy ? [] : value.match_notes.map((note) => ({ ...note, ...(note.athlete_journal ? { athlete_journal: consumeAthleteJournal(note.athlete_journal) } : {}) })),
    coach_notes: legacy ? [] : value.coach_notes.map((note) => ({ ...note, ...(note.athlete_journal ? { athlete_journal: consumeAthleteJournal(note.athlete_journal) } : {}) })),
    fan_notes: value.fan_notes.map((note) => ({ ...note, ...(note.athlete_journal ? { athlete_journal: consumeAthleteJournal(note.athlete_journal) } : {}) })),
  };
}

export function readFanLocalData(storage) {
  const raw = storage.getItem(FAN_LOCAL_DATA_KEY);
  if (raw === null) return emptyFanLocalData();
  return consumeFanLocalData(JSON.parse(raw));
}

export function writeFanLocalData(storage, value) {
  const accepted = consumeFanLocalData(value);
  const serialized = JSON.stringify(accepted);
  if (JSON.stringify(accepted, null, 2).length > MAX_BACKUP_CHARS) throw new Error('fan-local-backup-too-large');
  const existing = storage.getItem(FAN_LOCAL_DATA_KEY);
  if (existing !== null) {
    try { parseFanLocalDataBackup(existing); }
    catch { throw new Error('cannot-overwrite-unreadable-fan-data'); }
  }
  storage.setItem(FAN_LOCAL_DATA_KEY, serialized);
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

/** Prepare without writing. The exact original bytes prevent replacing later edits in this or another tab. */
export function prepareFanLocalDataImport(storage, text, references) {
  const next = validateFanLocalDataReferences(parseFanLocalDataBackup(text), references);
  const expectedRaw = storage.getItem(FAN_LOCAL_DATA_KEY);
  const current = expectedRaw === null ? emptyFanLocalData() : parseFanLocalDataBackup(expectedRaw);
  let conflicts = 0; let removed = 0;
  for (const key of ['training_notes', 'match_notes', 'coach_notes', 'fan_notes']) {
    for (const note of current[key]) {
      const incoming = next[key].find((row) => row.id === note.id);
      if (!incoming) removed++;
      else if (JSON.stringify(note) !== JSON.stringify(incoming)) conflicts++;
    }
  }
  return { expectedRaw, next, conflicts, removed, savedRemoved: current.saved_match_ids.filter((id) => !next.saved_match_ids.includes(id)).length,
    followedRemoved: current.followed_athlete_ids.filter((id) => !next.followed_athlete_ids.includes(id)).length };
}

export function commitFanLocalDataImport(storage, plan, confirmed = false) {
  if (confirmed !== true) throw new Error('import-confirmation-required');
  const accepted = consumeFanLocalData(plan.next);
  const serialized = serializeFanLocalDataBackup(accepted);
  if (serialized.length > MAX_BACKUP_CHARS) throw new Error('fan-local-backup-too-large');
  if (storage.getItem(FAN_LOCAL_DATA_KEY) !== plan.expectedRaw) throw new Error('import-current-data-changed');
  const recovery = JSON.stringify({ contract_version: 'ptti.fan-import-recovery/0.1', captured_at: new Date().toISOString(), data_raw: plan.expectedRaw });
  // If recovery cannot be saved or verified, never touch the live value.
  storage.setItem(FAN_LOCAL_RECOVERY_KEY, recovery);
  if (storage.getItem(FAN_LOCAL_RECOVERY_KEY) !== recovery) throw new Error('import-recovery-write-failed');
  storage.setItem(FAN_LOCAL_DATA_KEY, serialized);
  return accepted;
}

export function readFanImportRecovery(storage) {
  const raw = storage.getItem(FAN_LOCAL_RECOVERY_KEY);
  if (raw === null) return null;
  const snapshot = JSON.parse(raw);
  if (snapshot?.contract_version !== 'ptti.fan-import-recovery/0.1' || !(snapshot.data_raw === null || typeof snapshot.data_raw === 'string')) throw new Error('invalid-import-recovery');
  return snapshot.data_raw ?? serializeFanLocalDataBackup(emptyFanLocalData());
}
