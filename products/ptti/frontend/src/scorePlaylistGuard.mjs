/** Only server-owned score references participate; manual clips are untouched. */
export function scorePlaylistReferences(clips) {
  return clips.filter(clip => clip.event_type === 'MANUAL_SCORE_SEGMENT'
    && clip.source === 'MANUAL_CONFIRMED' && clip.score_moment_id
    && clip.evidence_id === `score:${clip.score_moment_id}`)
    .map(clip => ({ evidence_id: clip.evidence_id, score_revision: clip.score_revision ?? '' }));
}

export async function scoreRequestWithTimeout(operation, timeoutMs = 2500) {
  let deadline;
  try {
    return await Promise.race([operation(), new Promise((_, reject) => {
      deadline = setTimeout(() => reject(new Error('score validation timeout')), timeoutMs);
    })]);
  } finally { clearTimeout(deadline); }
}

/** A cached score row supplies identity only, never playable timestamps. */
export function loadLatestScoreClip(pointId, request, timeoutMs = 2500) {
  return scoreRequestWithTimeout(async () => {
    if (typeof pointId !== 'string' || !pointId) throw new Error('missing score identity');
    const queue = await request('/scores/playlist', [pointId], 'POST');
    const key = `score:${pointId}`;
    const expected = queue.score_references?.find(reference => reference.evidence_id === key);
    if (!expected?.score_revision || !queue.evidence_ids?.includes(key)) throw new Error('missing score revision');
    const clips = await request('/evidence');
    const clip = clips.find(candidate => candidate.evidence_id === key);
    const references = clip ? scorePlaylistReferences([clip]) : [];
    if (references.length !== 1 || references[0].score_revision !== expected.score_revision)
      throw new Error('score changed while loading');
    await request('/scores/playlist/validate', references, 'POST');
    return clip;
  }, timeoutMs);
}

/** Fail closed on a revision conflict or unavailable validation service. */
export function watchScorePlaylist(references, validate, invalidate, options = {}) {
  if (!references.length) return () => {};
  const schedule = options.schedule ?? setInterval;
  const cancel = options.cancel ?? clearInterval;
  let disposed = false, pending = false, deadline;
  const check = async () => {
    if (disposed || pending) return;
    pending = true;
    try {
      await Promise.race([validate(references), new Promise((_, reject) => {
        deadline = setTimeout(() => reject(new Error('score validation timeout')), options.timeoutMs ?? 2500);
      })]);
    }
    catch (error) {
      if (!disposed) { disposed = true; cancel(timer); invalidate(error); }
    } finally { clearTimeout(deadline); pending = false; }
  };
  const timer = schedule(check, options.intervalMs ?? 1000);
  void check();
  return () => { disposed = true; cancel(timer); clearTimeout(deadline); };
}
