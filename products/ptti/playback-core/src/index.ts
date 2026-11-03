/**
 * Browser-only local video playback and rally playlist control.
 *
 * The module never uploads a File. Callers hand it an HTMLVideoElement and a
 * user-selected File; the implementation uses an object URL and revokes it on
 * replacement or release.
 */

export type PlaybackRate = 0.5 | 1;

export type RallyBindingStatus =
  | 'BOUND'
  | 'PENDING_ANNOTATION'
  | 'UNBOUND'
  | 'STALE';

/** Times are seconds from the beginning of the selected video. */
export interface RallyPlaybackBinding {
  point_id: string;
  video_identity: string | null;
  start_time: number | null;
  end_time: number | null;
  binding_status: RallyBindingStatus;
}

export interface PlaybackFileInfo {
  name: string;
  type: string;
  size_bytes: number;
  last_modified_ms: number;
}

export type PlaybackStatus = 'empty' | 'loading' | 'ready' | 'error';
export type PlaylistStatus = 'playing' | 'paused' | 'completed' | 'cancelled' | 'failed';

export type PlaybackIssueCode =
  | 'invalid-file-type' | 'empty-file' | 'file-read-error' | 'identity-unavailable'
  | 'decode-error' | 'unsupported-media' | 'media-aborted' | 'duration-unavailable'
  | 'video-not-ready' | 'play-rejected' | 'playback-failed' | 'unsupported-rate'
  | 'invalid-rally' | 'not-bound' | 'video-mismatch' | 'missing-timestamp' | 'invalid-time'
  | 'time-out-of-range' | 'start-after-end' | 'empty-playlist' | 'repeat-requires-single'
  | 'seek-failed' | 'seek-timeout' | 'media-ended-early' | 'playlist-replaced' | 'cancelled';

export interface PlaybackIssue {
  code: PlaybackIssueCode;
  message: string;
}

export type PlaybackResult<T> =
  | { ok: true; value: T }
  | { ok: false; error: PlaybackIssue };

export interface PlaylistSnapshot {
  status: PlaylistStatus;
  current_index: number | null;
  total: number;
  point_id: string | null;
}

export interface PlaybackSnapshot {
  status: PlaybackStatus;
  video_identity: string | null;
  file: PlaybackFileInfo | null;
  duration_seconds: number | null;
  current_time_seconds: number;
  is_playing: boolean;
  playback_rate: PlaybackRate;
  error: PlaybackIssue | null;
  playlist: PlaylistSnapshot | null;
}

export interface RallyPlaylistOptions {
  /** Repeats forever and is accepted only for exactly one valid rally. */
  repeat_single?: boolean;
}

export interface RallyPlaylistTask {
  readonly done: Promise<
    | { status: 'completed'; completed_rallies: number }
    | { status: 'cancelled'; reason: string; completed_rallies: number }
    | { status: 'failed'; error: PlaybackIssue; completed_rallies: number }
  >;
  pause(): void;
  resume(): Promise<PlaybackResult<void>>;
  cancel(): void;
}

export interface LocalVideoPlaybackOptions {
  createObjectURL?: (file: File) => string;
  revokeObjectURL?: (url: string) => void;
  createVideoIdentity?: () => string;
  seek_timeout_ms?: number;
}

interface ActivePlaylist {
  rallies: RallyPlaybackBinding[];
  repeatSingle: boolean;
  currentIndex: number;
  completedRallies: number;
  transitioning: boolean;
  paused: boolean;
  settled: boolean;
  abort: AbortController;
  resolve: (result: Awaited<RallyPlaylistTask['done']>) => void;
}

const ISSUE_MESSAGES: Record<string, string> = {
  'invalid-file-type': '请选择 MP4 视频文件。',
  'empty-file': '所选视频文件为空。',
  'file-read-error': '无法读取此视频文件。请重新选择文件。',
  'identity-unavailable': '无法为当前视频建立本地身份，请刷新页面后重试。',
  'decode-error': '浏览器无法解码此视频。请检查文件是否损坏或编码是否受支持。',
  'unsupported-media': '浏览器无法识别此视频格式或编码。请尝试兼容的 MP4；文件损坏也可能导致此提示。',
  'media-aborted': '视频读取已中断，请重新选择文件后重试。',
  'duration-unavailable': '无法取得有效视频时长，暂不能按回合播放。请重新选择可正常读取的本地视频。',
  'video-not-ready': '请等待视频加载完成后再操作。',
  'play-rejected': '浏览器没有开始播放，请再点击一次播放。',
  'playback-failed': '浏览器无法完成播放操作，请重新选择本地视频后重试。',
  'unsupported-rate': '当前仅支持 0.5× 和 1× 播放速度。',
  'invalid-rally': '回合记录缺少有效的 point_id。',
  'not-bound': '该回合尚未绑定到当前视频。',
  'video-mismatch': '该回合绑定的是另一段视频，请重新核验时间。',
  'missing-timestamp': '该回合没有真实起止时间，请先人工标注。',
  'invalid-time': '回合时间必须是有效的非负秒数。',
  'time-out-of-range': '回合时间超出了视频长度。',
  'start-after-end': '回合开始时间不能晚于结束时间。',
  'empty-playlist': '没有可播放的回合。',
  'repeat-requires-single': '循环模式一次只能选择一个回合。',
  'seek-failed': '浏览器无法跳转到指定视频位置。',
  'seek-timeout': '视频定位超时，请稍后重试。',
  'media-ended-early': '视频在所标注回合结束前已停止播放，请重新核对时间范围。',
  'playlist-replaced': '连续回放已被新的回放任务替换。',
};

function issue(code: PlaybackIssueCode, message = ISSUE_MESSAGES[code] ?? '视频回放遇到问题。'): PlaybackIssue {
  return { code, message };
}

function ok<T>(value: T): PlaybackResult<T> {
  return { ok: true, value };
}

function fail<T = never>(code: PlaybackIssueCode): PlaybackResult<T> {
  return { ok: false, error: issue(code) };
}

function classifyPlayFailure(error: unknown): PlaybackIssueCode {
  const name = error && typeof error === 'object' && 'name' in error
    ? String((error as { name?: unknown }).name) : '';
  switch (name) {
    case 'NotAllowedError': return 'play-rejected';
    case 'NotSupportedError': return 'unsupported-media';
    case 'AbortError': return 'media-aborted';
    case 'NetworkError': return 'file-read-error';
    case 'InvalidStateError': return 'video-not-ready';
    default: return 'playback-failed';
  }
}

function finiteNonNegative(value: number | null): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

export function validateRallyPlaybackBinding(
  rally: RallyPlaybackBinding,
  videoIdentity: string,
  durationSeconds: number,
): PlaybackResult<void> {
  if (!rally || typeof rally.point_id !== 'string' || rally.point_id.trim() === '') {
    return fail('invalid-rally');
  }
  if (rally.binding_status !== 'BOUND' || !rally.video_identity) return fail('not-bound');
  if (rally.video_identity !== videoIdentity) return fail('video-mismatch');
  if (rally.start_time === null || rally.end_time === null) return fail('missing-timestamp');
  if (!finiteNonNegative(rally.start_time) || !finiteNonNegative(rally.end_time)) return fail('invalid-time');
  if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) return fail('video-not-ready');
  if (rally.start_time > durationSeconds || rally.end_time > durationSeconds) return fail('time-out-of-range');
  if (rally.start_time > rally.end_time) return fail('start-after-end');
  return ok(undefined);
}

/** Returns copied records and marks video-bound timestamps stale after replacement. */
export function revalidateRallyBindings(
  rallies: readonly RallyPlaybackBinding[],
  videoIdentity: string,
  durationSeconds: number,
): RallyPlaybackBinding[] {
  return rallies.map((rally) => {
    if (rally.binding_status !== 'BOUND') return { ...rally };
    if (rally.video_identity !== videoIdentity) return { ...rally, binding_status: 'STALE' };
    const validation = validateRallyPlaybackBinding(rally, videoIdentity, durationSeconds);
    return validation.ok ? { ...rally } : { ...rally, binding_status: 'PENDING_ANNOTATION' };
  });
}

function defaultIdentity(): string {
  return `local-session:${globalThis.crypto.randomUUID()}`;
}

function copyFileInfo(file: File): PlaybackFileInfo {
  return {
    name: file.name,
    type: file.type,
    size_bytes: file.size,
    last_modified_ms: file.lastModified,
  };
}

function waitForSeek(
  video: HTMLVideoElement,
  targetSeconds: number,
  timeoutMs: number,
  signal: AbortSignal,
): Promise<void> {
  return new Promise((resolve, reject) => {
    let settled = false;
    const cleanup = () => {
      clearTimeout(timer);
      video.removeEventListener('seeked', onSeeked);
      video.removeEventListener('error', onError);
      signal.removeEventListener('abort', onAbort);
    };
    const finish = (error?: PlaybackIssue) => {
      if (settled) return;
      settled = true;
      cleanup();
      if (error) reject(error);
      else resolve();
    };
    const onSeeked = () => {
      if (Math.abs(video.currentTime - targetSeconds) <= 0.1) finish();
    };
    const onError = () => finish(issue('seek-failed'));
    const onAbort = () => finish(issue('cancelled'));
    const timer = setTimeout(() => finish(issue('seek-timeout')), timeoutMs);

    if (signal.aborted) {
      finish(issue('cancelled'));
      return;
    }
    if (Math.abs(video.currentTime - targetSeconds) <= 0.01 && !video.seeking) {
      finish();
      return;
    }
    video.addEventListener('seeked', onSeeked);
    video.addEventListener('error', onError);
    signal.addEventListener('abort', onAbort, { once: true });
    try {
      video.currentTime = targetSeconds;
      if (Math.abs(video.currentTime - targetSeconds) <= 0.01 && !video.seeking) queueMicrotask(onSeeked);
    } catch {
      finish(issue('seek-failed'));
    }
  });
}

export class LocalVideoPlaybackController {
  private readonly createUrl: (file: File) => string;
  private readonly revokeUrl: (url: string) => void;
  private readonly createIdentity: () => string;
  private readonly seekTimeoutMs: number;
  private readonly listeners = new Set<(snapshot: PlaybackSnapshot) => void>();
  private objectUrl: string | null = null;
  private activePlaylist: ActivePlaylist | null = null;
  private state: PlaybackSnapshot = {
    status: 'empty',
    video_identity: null,
    file: null,
    duration_seconds: null,
    current_time_seconds: 0,
    is_playing: false,
    playback_rate: 1,
    error: null,
    playlist: null,
  };
  private disposed = false;

  constructor(private readonly video: HTMLVideoElement, options: LocalVideoPlaybackOptions = {}) {
    this.createUrl = options.createObjectURL ?? ((file) => URL.createObjectURL(file));
    this.revokeUrl = options.revokeObjectURL ?? ((url) => URL.revokeObjectURL(url));
    this.createIdentity = options.createVideoIdentity ?? defaultIdentity;
    const configuredSeekTimeout = options.seek_timeout_ms;
    this.seekTimeoutMs = Number.isFinite(configuredSeekTimeout) && configuredSeekTimeout! > 0
      ? configuredSeekTimeout! : 5000;
    video.addEventListener('loadedmetadata', this.handleMetadata);
    video.addEventListener('canplay', this.handleCanPlay);
    video.addEventListener('timeupdate', this.handleTimeUpdate);
    video.addEventListener('play', this.handlePlay);
    video.addEventListener('pause', this.handlePause);
    video.addEventListener('seeked', this.handleSeeked);
    video.addEventListener('ended', this.handleEnded);
    video.addEventListener('error', this.handleMediaError);
  }

  getSnapshot(): PlaybackSnapshot {
    return { ...this.state, file: this.state.file ? { ...this.state.file } : null,
      playlist: this.state.playlist ? { ...this.state.playlist } : null,
      error: this.state.error ? { ...this.state.error } : null };
  }

  subscribe(listener: (snapshot: PlaybackSnapshot) => void): () => void {
    if (this.disposed) return () => undefined;
    this.listeners.add(listener);
    listener(this.getSnapshot());
    return () => this.listeners.delete(listener);
  }

  loadFile(file: File): PlaybackResult<string> {
    if (this.disposed) return fail('file-read-error');
    this.detachCurrentSource('video-replaced');
    try { this.video.playbackRate = 1; } catch { /* The file load will report media capability failures. */ }
    this.setState({ status: 'empty', video_identity: null, file: null, duration_seconds: null,
      current_time_seconds: 0, is_playing: false, playback_rate: 1, error: null, playlist: null });

    const name = typeof file?.name === 'string' ? file.name : '';
    const type = typeof file?.type === 'string' ? file.type : '';
    if (!name.toLowerCase().endsWith('.mp4') || (type !== '' && type !== 'video/mp4')) {
      const error = issue('invalid-file-type');
      this.setState({ status: 'error', error });
      return { ok: false, error };
    }
    if (!Number.isFinite(file.size) || file.size <= 0) {
      const error = issue('empty-file');
      this.setState({ status: 'error', error });
      return { ok: false, error };
    }

    let videoIdentity: string;
    try {
      videoIdentity = this.createIdentity();
      if (typeof videoIdentity !== 'string' || videoIdentity.trim() === '') throw new Error('empty video identity');
    } catch {
      const error = issue('identity-unavailable');
      this.setState({ status: 'error', error });
      return { ok: false, error };
    }

    let nextUrl: string;
    try {
      nextUrl = this.createUrl(file);
    } catch {
      const error = issue('file-read-error');
      this.setState({ status: 'error', error });
      return { ok: false, error };
    }
    this.objectUrl = nextUrl;
    this.setState({ status: 'loading', video_identity: videoIdentity, file: copyFileInfo(file),
      duration_seconds: null, current_time_seconds: 0, playback_rate: 1, error: null, playlist: null });
    try {
      this.video.src = nextUrl;
      this.video.load();
    } catch {
      this.handleLoadFailure('file-read-error');
      return fail('file-read-error');
    }
    return ok(videoIdentity);
  }

  async play(): Promise<PlaybackResult<void>> {
    if (this.state.status !== 'ready' || !this.objectUrl) return fail('video-not-ready');
    try {
      await this.video.play();
      return ok(undefined);
    } catch (error) {
      return fail(classifyPlayFailure(error));
    }
  }

  pause(): void {
    if (this.disposed) return;
    this.video.pause();
  }

  seek(seconds: number): PlaybackResult<number> {
    if (this.state.status !== 'ready' || this.state.duration_seconds === null) return fail('video-not-ready');
    if (!Number.isFinite(seconds)) return fail('invalid-time');
    const clamped = Math.min(this.state.duration_seconds, Math.max(0, seconds));
    try {
      this.video.currentTime = clamped;
      // An explicit seek is a user navigation decision. Do not let an older
      // playlist advance and pull playback back to one of its later entries.
      this.cancelActivePlaylist('manual-seek');
      this.setState({ current_time_seconds: clamped });
      return ok(clamped);
    } catch {
      return fail('seek-failed');
    }
  }

  setPlaybackRate(rate: number): PlaybackResult<PlaybackRate> {
    if (this.state.status !== 'ready') return fail('video-not-ready');
    if (rate !== 0.5 && rate !== 1) return fail('unsupported-rate');
    try {
      this.video.playbackRate = rate;
      this.setState({ playback_rate: rate });
      return ok(rate);
    } catch {
      return fail('unsupported-rate');
    }
  }

  playRallyPlaylist(
    rallies: readonly RallyPlaybackBinding[],
    options: RallyPlaylistOptions = {},
  ): PlaybackResult<RallyPlaylistTask> {
    // A playlist call is an explicit selection/replacement command. Stop the
    // previous comparison before validating the new selection so a stale or
    // otherwise invalid click cannot leave the older clip playing.
    this.cancelActivePlaylist('playlist-replaced');
    if (this.state.status !== 'ready' || !this.state.video_identity || this.state.duration_seconds === null) {
      return fail('video-not-ready');
    }
    if (rallies.length === 0) return fail('empty-playlist');
    if (options.repeat_single && rallies.length !== 1) return fail('repeat-requires-single');
    for (const rally of rallies) {
      const validation = validateRallyPlaybackBinding(rally, this.state.video_identity, this.state.duration_seconds);
      if (!validation.ok) return validation;
    }

    let resolveDone!: (result: Awaited<RallyPlaylistTask['done']>) => void;
    const done = new Promise<Awaited<RallyPlaylistTask['done']>>((resolve) => { resolveDone = resolve; });
    const active: ActivePlaylist = {
      rallies: rallies.map((rally) => ({ ...rally })),
      repeatSingle: Boolean(options.repeat_single),
      currentIndex: 0,
      completedRallies: 0,
      transitioning: false,
      paused: false,
      settled: false,
      abort: new AbortController(),
      resolve: resolveDone,
    };
    this.activePlaylist = active;
    this.publishPlaylist(active, 'playing');
    const task: RallyPlaylistTask = {
      done,
      pause: () => this.pausePlaylist(active),
      resume: () => this.resumePlaylist(active),
      cancel: () => this.finishPlaylist(active, { status: 'cancelled', reason: 'cancelled-by-user', completed_rallies: active.completedRallies }),
    };
    void this.startRally(active, 0);
    return ok(task);
  }

  release(): void {
    if (this.disposed) return;
    this.detachCurrentSource('released');
    this.video.removeEventListener('loadedmetadata', this.handleMetadata);
    this.video.removeEventListener('canplay', this.handleCanPlay);
    this.video.removeEventListener('timeupdate', this.handleTimeUpdate);
    this.video.removeEventListener('play', this.handlePlay);
    this.video.removeEventListener('pause', this.handlePause);
    this.video.removeEventListener('seeked', this.handleSeeked);
    this.video.removeEventListener('ended', this.handleEnded);
    this.video.removeEventListener('error', this.handleMediaError);
    this.disposed = true;
    this.listeners.clear();
    this.state = { status: 'empty', video_identity: null, file: null, duration_seconds: null,
      current_time_seconds: 0, is_playing: false, playback_rate: 1, error: null, playlist: null };
  }

  private detachCurrentSource(reason: string): void {
    this.cancelActivePlaylist(reason);
    try {
      this.video.pause();
      this.video.removeAttribute('src');
      this.video.load();
    } catch {
      // Detaching remains best-effort; revoking the owned object URL is required.
    }
    if (this.objectUrl) this.revokeUrl(this.objectUrl);
    this.objectUrl = null;
  }

  private setState(patch: Partial<PlaybackSnapshot>): void {
    this.state = { ...this.state, ...patch };
    const snapshot = this.getSnapshot();
    for (const listener of this.listeners) listener(snapshot);
  }

  private handleMetadata = (): void => {
    if (!this.isCurrentSource() || this.video.readyState < 1) return;
    const duration = this.video.duration;
    if (!Number.isFinite(duration) || duration <= 0) {
      this.handleLoadFailure('duration-unavailable');
      return;
    }
    this.setState({ duration_seconds: duration });
  };

  private handleCanPlay = (): void => {
    if (this.isCurrentSource() && this.video.readyState >= 3
      && this.state.status === 'loading' && this.state.duration_seconds !== null) {
      this.setState({ status: 'ready', error: null });
    }
  };

  private handleTimeUpdate = (): void => {
    if (!this.isCurrentSource() || this.state.status !== 'ready') return;
    const current = Number.isFinite(this.video.currentTime) ? Math.max(0, this.video.currentTime) : 0;
    this.setState({ current_time_seconds: current });
    this.advanceWhenRallyEnds();
  };

  private handlePlay = (): void => {
    if (!this.isCurrentSource()) return;
    this.setState({ is_playing: true });
    const active = this.activePlaylist;
    if (active && !active.transitioning && !active.paused && this.isActive(active)) this.publishPlaylist(active, 'playing');
  };

  private handlePause = (): void => {
    if (!this.isCurrentSource()) return;
    this.setState({ is_playing: false });
    const active = this.activePlaylist;
    if (active && !active.transitioning && this.isActive(active)) this.publishPlaylist(active, 'paused');
  };

  private handleSeeked = (): void => {
    if (!this.isCurrentSource() || this.state.status !== 'ready') return;
    const current = Number.isFinite(this.video.currentTime) ? Math.max(0, this.video.currentTime) : 0;
    this.setState({ current_time_seconds: current });
  };

  private handleEnded = (): void => {
    if (!this.isCurrentSource()) return;
    const active = this.activePlaylist;
    if (!active || active.transitioning || active.paused) return;
    const rally = active.rallies[active.currentIndex];
    if (this.video.currentTime + 0.1 >= (rally.end_time ?? Infinity)) this.advancePlaylist(active);
    else this.finishPlaylist(active, { status: 'failed', error: issue('media-ended-early'), completed_rallies: active.completedRallies });
  };

  private handleMediaError = (): void => {
    if (!this.isCurrentSource() || this.state.status === 'empty' || this.state.status === 'error') return;
    // MediaError describes the browser failure stage, not a diagnosis that the
    // user's file is corrupt. Preserve the ambiguous fallback when unavailable.
    const code = this.video.error?.code;
    this.handleLoadFailure(code === 1 ? 'media-aborted' : code === 2 ? 'file-read-error'
      : code === 4 ? 'unsupported-media' : 'decode-error');
  };

  private handleLoadFailure(code: PlaybackIssueCode): void {
    const error = issue(code);
    this.setState({ status: 'error', error });
    const active = this.activePlaylist;
    if (active) this.finishPlaylist(active, { status: 'failed', error, completed_rallies: active.completedRallies });
  }

  private pausePlaylist(active: ActivePlaylist): void {
    if (!this.isActive(active) || active.paused) return;
    active.paused = true;
    this.video.pause();
    this.publishPlaylist(active, 'paused');
  }

  private async resumePlaylist(active: ActivePlaylist): Promise<PlaybackResult<void>> {
    if (!this.isActive(active)) return fail('video-not-ready');
    active.paused = false;
    this.publishPlaylist(active, 'playing');
    if (active.transitioning) return ok(undefined);
    const result = await this.play();
    if (!result.ok) {
      this.finishPlaylist(active, { status: 'failed', error: result.error, completed_rallies: active.completedRallies });
      return result;
    }
    this.advanceWhenRallyEnds();
    return ok(undefined);
  }

  private async startRally(active: ActivePlaylist, index: number): Promise<void> {
    if (!this.isActive(active)) return;
    active.currentIndex = index;
    active.transitioning = true;
    const rally = active.rallies[index];
    this.publishPlaylist(active, 'playing');
    try {
      await waitForSeek(this.video, rally.start_time!, this.seekTimeoutMs, active.abort.signal);
    } catch (error) {
      if (!this.isActive(active)) return;
      const seekIssue = error && typeof error === 'object' && 'code' in error
        ? error as PlaybackIssue : issue('seek-failed');
      this.finishPlaylist(active, { status: 'failed', error: seekIssue, completed_rallies: active.completedRallies });
      return;
    }
    if (!this.isActive(active)) return;
    active.transitioning = false;
    if (active.paused) return;
    const result = await this.play();
    if (!this.isActive(active)) return;
    if (!result.ok) {
      this.finishPlaylist(active, { status: 'failed', error: result.error, completed_rallies: active.completedRallies });
      return;
    }
    this.advanceWhenRallyEnds();
  }

  private advanceWhenRallyEnds(): void {
    const active = this.activePlaylist;
    if (!active || active.paused || active.transitioning || !this.isActive(active)) return;
    const rally = active.rallies[active.currentIndex];
    if (this.video.currentTime + 0.02 >= rally.end_time!) this.advancePlaylist(active);
  }

  private advancePlaylist(active: ActivePlaylist): void {
    if (!this.isActive(active) || active.transitioning || active.paused) return;
    active.completedRallies += 1;
    this.video.pause();
    if (active.repeatSingle) {
      void this.startRally(active, 0);
      return;
    }
    const nextIndex = active.currentIndex + 1;
    if (nextIndex >= active.rallies.length) {
      this.finishPlaylist(active, { status: 'completed', completed_rallies: active.completedRallies });
      return;
    }
    void this.startRally(active, nextIndex);
  }

  private cancelActivePlaylist(reason: string): void {
    const active = this.activePlaylist;
    if (active) this.finishPlaylist(active, { status: 'cancelled', reason, completed_rallies: active.completedRallies });
  }

  private finishPlaylist(active: ActivePlaylist, result: Awaited<RallyPlaylistTask['done']>): void {
    if (active.settled) return;
    active.settled = true;
    active.abort.abort();
    if (this.activePlaylist === active) this.activePlaylist = null;
    try { this.video.pause(); } catch { /* Media element may already be detached. */ }
    const status: PlaylistStatus = result.status;
    const rally = active.rallies[active.currentIndex];
    this.setState({ playlist: { status, current_index: active.currentIndex, total: active.rallies.length,
      point_id: rally?.point_id ?? null } });
    active.resolve(result);
  }

  private publishPlaylist(active: ActivePlaylist, status: 'playing' | 'paused'): void {
    if (!this.isActive(active)) return;
    const rally = active.rallies[active.currentIndex];
    this.setState({ playlist: { status, current_index: active.currentIndex, total: active.rallies.length,
      point_id: rally?.point_id ?? null } });
  }

  private isActive(active: ActivePlaylist): boolean {
    return this.activePlaylist === active && !active.settled && !this.disposed;
  }

  private isCurrentSource(): boolean {
    if (!this.objectUrl) return false;
    const currentSrc = this.video.currentSrc;
    // `currentSrc` may be temporarily empty while the browser selects a new
    // resource. Treat that gap as unowned: queued events from the detached
    // video must not mark the replacement ready or move its playhead.
    return currentSrc === this.objectUrl;
  }
}

export function createLocalVideoPlaybackController(
  video: HTMLVideoElement,
  options?: LocalVideoPlaybackOptions,
): LocalVideoPlaybackController {
  return new LocalVideoPlaybackController(video, options);
}
