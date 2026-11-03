declare module '@ptti/playback-core' {
  export type RallyBindingStatus = 'BOUND' | 'PENDING_ANNOTATION' | 'UNBOUND' | 'STALE';
  export interface RallyPlaybackBinding {
    point_id: string;
    video_identity: string | null;
    start_time: number | null;
    end_time: number | null;
    binding_status: RallyBindingStatus;
  }
  export interface PlaybackIssue { code: string; message: string }
  export type PlaybackResult<T> = { ok: true; value: T } | { ok: false; error: PlaybackIssue };
  export interface PlaylistSnapshot {
    status: 'playing' | 'paused' | 'completed' | 'cancelled' | 'failed';
    current_index: number | null;
    total: number;
    point_id: string | null;
  }
  export interface PlaybackSnapshot {
    status: 'empty' | 'loading' | 'ready' | 'error';
    video_identity: string | null;
    file: { name: string; type: string; size_bytes: number; last_modified_ms: number } | null;
    duration_seconds: number | null;
    current_time_seconds: number;
    is_playing: boolean;
    playback_rate: 0.5 | 1;
    error: PlaybackIssue | null;
    playlist: PlaylistSnapshot | null;
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
  export class LocalVideoPlaybackController {
    constructor(video: HTMLVideoElement, options?: { createObjectURL?: (file: File) => string; revokeObjectURL?: (url: string) => void; createVideoIdentity?: () => string; seek_timeout_ms?: number });
    getSnapshot(): PlaybackSnapshot;
    subscribe(listener: (snapshot: PlaybackSnapshot) => void): () => void;
    loadFile(file: File): PlaybackResult<string>;
    play(): Promise<PlaybackResult<void>>;
    pause(): void;
    seek(seconds: number): PlaybackResult<number>;
    setPlaybackRate(rate: number): PlaybackResult<0.5 | 1>;
    playRallyPlaylist(rallies: readonly RallyPlaybackBinding[]): PlaybackResult<RallyPlaylistTask>;
    release(): void;
  }
}
