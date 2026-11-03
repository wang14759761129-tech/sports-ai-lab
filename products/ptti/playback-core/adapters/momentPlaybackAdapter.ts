/** Adapter for an already-loaded Playback Core and its HTML media element. */
export type AdapterError = 'not-ready' | 'identity-mismatch' | 'invalid-time' | 'out-of-range' | 'cancelled' | 'seek-timeout' | 'media-error' | 'seek-failed' | 'play-failed';
export type Result<T> = { ok: true; value: T } | { ok: false; error: AdapterError };
type Core = {
  getSnapshot(): { status: string; video_identity: string | null; duration_seconds: number | null };
  seek(seconds: number): { ok: boolean };
  play(): Promise<{ ok: boolean }>;
  pause(): void;
};
export type AdapterState = { status: 'unloaded' | 'ready' | 'seeking' | 'seeked' | 'error'; currentTime: number | null; error: AdapterError | null };
const ok = <T>(value: T): Result<T> => ({ ok: true, value });
const fail = <T>(error: AdapterError): Result<T> => ({ ok: false, error });

export class MomentPlaybackAdapter {
  private identity: string | null = null;
  private pending: (() => void) | null = null;
  private listeners = new Set<(state: AdapterState) => void>();
  private state: AdapterState = { status: 'unloaded', currentTime: null, error: null };
  constructor(private core: Core, private media: HTMLMediaElement, private timeoutMs = 12000) {}
  private emit(status: AdapterState['status'], error: AdapterError | null = null) {
    this.state = { status, currentTime: this.identity && Number.isFinite(this.media.currentTime) ? this.media.currentTime : null, error };
    for (const listener of this.listeners) listener({ ...this.state });
  }
  subscribeState(listener: (state: AdapterState) => void): () => void {
    this.listeners.add(listener); listener({ ...this.state }); return () => this.listeners.delete(listener);
  }
  /** Identity must be the same identity independently associated with the loaded Core session. */
  load(mediaIdentity: string): Result<void> {
    this.cancelPendingSeek(); this.identity = null;
    const snapshot = this.core.getSnapshot();
    if (snapshot.status !== 'ready' || this.media.readyState < 1 || this.media.error) { this.emit('error', 'not-ready'); return fail('not-ready'); }
    if (!mediaIdentity || snapshot.video_identity !== mediaIdentity) { this.emit('error', 'identity-mismatch'); return fail('identity-mismatch'); }
    this.identity = mediaIdentity; this.emit('ready'); return ok(undefined);
  }
  private check(): AdapterError | null {
    const s = this.core.getSnapshot();
    if (!this.identity || s.video_identity !== this.identity) return 'identity-mismatch';
    if (this.media.error) return 'media-error';
    if (s.status !== 'ready' || this.media.readyState < 1 || !Number.isFinite(s.duration_seconds)) return 'not-ready';
    return null;
  }
  getCurrentTime(): Result<number> {
    const error = this.check(); if (error) return fail(error);
    return Number.isFinite(this.media.currentTime) ? ok(this.media.currentTime) : fail('not-ready');
  }
  async play(): Promise<Result<void>> {
    const error = this.check(); if (error) { this.emit('error', error); return fail(error); }
    try { const result = await this.core.play(); if (!result.ok) { this.emit('error', 'play-failed'); return fail('play-failed'); } return ok(undefined); }
    catch { this.emit('error', 'play-failed'); return fail('play-failed'); }
  }
  pause(): Result<void> {
    const error = this.check(); if (error) { this.emit('error', error); return fail(error); }
    try { this.core.pause(); return ok(undefined); } catch { this.emit('error', 'media-error'); return fail('media-error'); }
  }
  cancelPendingSeek(): void { this.pending?.(); }
  seekWithPreRoll(seconds: number, preRollSeconds: number): Promise<Result<number>> {
    this.cancelPendingSeek();
    if (!Number.isFinite(seconds) || !Number.isFinite(preRollSeconds) || preRollSeconds < 0 || seconds < 0) { this.emit('error', 'invalid-time'); return Promise.resolve(fail('invalid-time')); }
    const duration = this.core.getSnapshot().duration_seconds;
    if (duration !== null && seconds > duration) { this.emit('error', 'out-of-range'); return Promise.resolve(fail('out-of-range')); }
    return this.seekExact(Math.max(0, seconds - preRollSeconds));
  }
  seekExact(seconds: number): Promise<Result<number>> {
    this.cancelPendingSeek();
    const error = this.check(); if (error) { this.emit('error', error); return Promise.resolve(fail(error)); }
    if (!Number.isFinite(seconds)) { this.emit('error', 'invalid-time'); return Promise.resolve(fail('invalid-time')); }
    const duration = this.core.getSnapshot().duration_seconds!;
    if (seconds < 0 || seconds > duration) { this.emit('error', 'out-of-range'); return Promise.resolve(fail('out-of-range')); }
    const alreadyThere = !this.media.seeking && Math.abs(this.media.currentTime - seconds) <= 0.01;
    this.emit('seeking');
    return new Promise(resolve => {
      let done = false;
      const finish = (error?: AdapterError) => {
        if (done) return; done = true; clearTimeout(timer);
        this.media.removeEventListener('seeked', onSeeked); this.media.removeEventListener('error', onError);
        this.pending = null;
        if (error) { this.emit(error === 'cancelled' ? 'ready' : 'error', error); resolve(fail(error)); }
        else { this.emit('seeked'); resolve(ok(this.media.currentTime)); }
      };
      const onSeeked = () => { const currentError = this.check(); if (currentError) finish(currentError); else if (!this.media.seeking && Math.abs(this.media.currentTime - seconds) <= 0.1) finish(); };
      const onError = () => finish('media-error');
      const timer = setTimeout(() => finish('seek-timeout'), this.timeoutMs);
      this.pending = () => finish('cancelled');
      this.media.addEventListener('seeked', onSeeked); this.media.addEventListener('error', onError);
      try {
        if (!this.core.seek(seconds).ok) finish('seek-failed');
        else if (alreadyThere && !this.media.seeking && Math.abs(this.media.currentTime - seconds) <= 0.01) finish();
      } catch { finish('seek-failed'); }
    });
  }
}
