import { quickMillisecondsToLocalSeconds } from './local-video-review.mjs';

const finiteNonNegativeInteger = (value) => Number.isSafeInteger(value) && value >= 0;

export function playbackIssueMessageKey(code) {
  if (code === 'cancelled' || code === 'playlist-replaced') return '';
  const keys = {
    'play-rejected': 'pro.video.playRejected',
    'seek-failed': 'pro.video.seekFailed',
    'seek-timeout': 'pro.video.seekTimeout',
    'invalid-file-type': 'pro.video.fileTypeError',
    'empty-file': 'pro.video.fileUnreadable',
    'file-read-error': 'pro.video.readFailed',
    'media-aborted': 'pro.video.readAborted',
    'unsupported-media': 'pro.video.unsupportedMedia',
    'decode-error': 'pro.video.decodeFailed',
    'duration-unavailable': 'pro.video.durationUnavailable',
    'video-not-ready': 'pro.video.videoNotReady',
    'time-out-of-range': 'pro.video.timeOutOfRange',
    'video-mismatch': 'pro.video.identityMismatch',
    'identity-unavailable': 'pro.video.identityUnavailable',
    'not-bound': 'pro.video.confirmRangeFirst',
    'missing-timestamp': 'pro.video.confirmRangeFirst',
    'invalid-time': 'pro.video.confirmRangeFirst',
    'start-after-end': 'pro.video.confirmRangeFirst',
  };
  return Object.hasOwn(keys, code) ? keys[code] : 'pro.video.playbackFailed';
}

/** Adapt contract milliseconds to Playback Core seconds without elevating evidence. */
export function toRallyPlaybackBinding(point, binding) {
  const startMs = point?.rally_start_ms;
  const endMs = point?.rally_end_ms;
  const startTime = finiteNonNegativeInteger(startMs) ? quickMillisecondsToLocalSeconds(startMs) : null;
  const endTime = finiteNonNegativeInteger(endMs) ? quickMillisecondsToLocalSeconds(endMs) : null;
  const currentIdentity = typeof binding?.current_video_identity === 'string' ? binding.current_video_identity : '';
  const pointIdentity = typeof binding?.bound_video_identity === 'string' ? binding.bound_video_identity : '';
  const duration = binding?.duration_seconds;

  let bindingStatus = 'UNBOUND';
  if (pointIdentity && currentIdentity && pointIdentity !== currentIdentity) bindingStatus = 'STALE';
  else if (pointIdentity && currentIdentity && pointIdentity === currentIdentity) {
    const validDuration = Number.isFinite(duration) && duration > 0;
    const validRange = startTime !== null && endTime !== null && startTime < endTime
      && validDuration && endTime <= duration;
    if (binding.start_confirmed === true && binding.end_confirmed === true && validRange) bindingStatus = 'BOUND';
    else bindingStatus = 'PENDING_ANNOTATION';
  }

  return {
    point_id: typeof point?.point_id === 'string' ? point.point_id : '',
    video_identity: pointIdentity || null,
    start_time: startTime,
    end_time: endTime,
    binding_status: bindingStatus,
  };
}

export function toRallyPlaybackBindings(points, binding) {
  if (!Array.isArray(points)) return [];
  return points.map((point) => toRallyPlaybackBinding(point, binding));
}
