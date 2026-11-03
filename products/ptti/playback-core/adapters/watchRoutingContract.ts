/**
 * GOAL14 watch routing contract. This is an adapter contract, not a player and
 * not part of the pinned Playback Core source at src/index.ts.
 * It decides whether a caller may present a viewing route; it never opens it.
 */
export const WATCH_ROUTING_CONTRACT = 'ptti.watch-routing/0.1' as const;

export const WATCH_ROUTE_MODES = [
  'OFFICIAL_EMBED',
  'OFFICIAL_PAGE',
  'AUTHORIZED_SOURCE',
  'REPLAY',
  'LIVE_SCORE',
] as const;

export type WatchRouteMode = typeof WATCH_ROUTE_MODES[number];
export type ViewingPermission = 'PUBLIC_PLATFORM_PAGE' | 'AUTHORIZED' | 'UNKNOWN' | 'DENIED';
export type PlaybackEvidence = 'VERIFIED' | 'NOT_TESTED' | 'FAILED';

export interface WatchRouteCandidate {
  mode: WatchRouteMode;
  /** A reviewed source reference; this does not prove current availability. */
  sourceReference: 'VERIFIED' | 'UNKNOWN' | 'MISSING';
  viewingPermission: ViewingPermission;
  playbackEvidence?: PlaybackEvidence;
  playbackType?: 'OFFICIAL_EMBED' | 'OFFICIAL_PAGE' | 'AUTHORIZED_STREAM' | 'AUTHORIZED_REPLAY' | 'LOCAL';
  embedPermission?: 'ALLOWED' | 'UNKNOWN' | 'DENIED';
  rightsEvidence?: 'VERIFIED' | 'UNKNOWN' | 'MISSING';
  localMedia?: 'AVAILABLE' | 'MISSING' | 'CHANGED' | 'UNKNOWN';
  replayType?: 'AUTHORIZED_ON_DEMAND' | 'LOCAL_FILE';
  localSelection?: 'USER_SELECTED' | 'NOT_SELECTED';
  localViewingConfirmation?: 'USER_CONFIRMED' | 'UNKNOWN' | 'DENIED';
  liveScore?: 'LIVE_VERIFIED' | 'NOT_LIVE' | 'UNKNOWN';
}

export type WatchRouteReason =
  | 'ROUTE_ELIGIBLE'
  | 'SOURCE_REFERENCE_UNVERIFIED'
  | 'SOURCE_REFERENCE_MISSING'
  | 'VIEW_PERMISSION_UNKNOWN'
  | 'VIEW_PERMISSION_DENIED'
  | 'ROUTE_TYPE_MISMATCH'
  | 'EMBED_PERMISSION_UNKNOWN'
  | 'EMBED_PERMISSION_DENIED'
  | 'RIGHTS_EVIDENCE_REQUIRED'
  | 'LOCAL_MEDIA_UNAVAILABLE'
  | 'LOCAL_MEDIA_NOT_SELECTED'
  | 'LOCAL_VIEW_PERMISSION_UNKNOWN'
  | 'LOCAL_VIEW_PERMISSION_DENIED'
  | 'LIVE_SCORE_UNVERIFIED';

export interface WatchRouteDecision {
  contract: typeof WATCH_ROUTING_CONTRACT;
  mode: WatchRouteMode;
  state: 'ELIGIBLE' | 'SCORE_ONLY' | 'BLOCKED';
  playbackEvidence: PlaybackEvidence;
  reason: WatchRouteReason;
}

function decision(
  candidate: WatchRouteCandidate,
  state: WatchRouteDecision['state'],
  reason: WatchRouteReason,
): WatchRouteDecision {
  return {
    contract: WATCH_ROUTING_CONTRACT,
    mode: candidate.mode,
    state,
    playbackEvidence: candidate.playbackEvidence === 'VERIFIED' || candidate.playbackEvidence === 'FAILED'
      ? candidate.playbackEvidence
      : 'NOT_TESTED',
    reason,
  };
}

function sourceReferenceFailure(candidate: WatchRouteCandidate): WatchRouteReason | null {
  if (candidate.sourceReference === 'VERIFIED') return null;
  return candidate.sourceReference === 'MISSING' ? 'SOURCE_REFERENCE_MISSING' : 'SOURCE_REFERENCE_UNVERIFIED';
}

function viewingPermissionFailure(candidate: WatchRouteCandidate): WatchRouteReason | null {
  if (candidate.viewingPermission === 'DENIED') return 'VIEW_PERMISSION_DENIED';
  if (candidate.viewingPermission === 'UNKNOWN') return 'VIEW_PERMISSION_UNKNOWN';
  return null;
}

function publicOrAuthorized(candidate: WatchRouteCandidate): boolean {
  return candidate.viewingPermission === 'PUBLIC_PLATFORM_PAGE' || candidate.viewingPermission === 'AUTHORIZED';
}

/** Evaluate one explicit route. It does not open URLs or silently choose a fallback. */
export function evaluateWatchRoute(input: unknown): WatchRouteDecision | null {
  if (!input || typeof input !== 'object') return null;
  const candidate = input as WatchRouteCandidate;
  if (!WATCH_ROUTE_MODES.includes(candidate.mode)) return null;
  const referenceFailure = sourceReferenceFailure(candidate);
  const permissionFailure = viewingPermissionFailure(candidate);

  switch (candidate.mode) {
    case 'OFFICIAL_EMBED': {
      if (referenceFailure) return decision(candidate, 'BLOCKED', referenceFailure);
      if (permissionFailure) return decision(candidate, 'BLOCKED', permissionFailure);
      if (!publicOrAuthorized(candidate)) return decision(candidate, 'BLOCKED', 'VIEW_PERMISSION_UNKNOWN');
      if (candidate.playbackType !== 'OFFICIAL_EMBED') return decision(candidate, 'BLOCKED', 'ROUTE_TYPE_MISMATCH');
      if (candidate.embedPermission === 'DENIED') return decision(candidate, 'BLOCKED', 'EMBED_PERMISSION_DENIED');
      if (candidate.embedPermission !== 'ALLOWED') return decision(candidate, 'BLOCKED', 'EMBED_PERMISSION_UNKNOWN');
      return decision(candidate, 'ELIGIBLE', 'ROUTE_ELIGIBLE');
    }
    case 'OFFICIAL_PAGE': {
      if (referenceFailure) return decision(candidate, 'BLOCKED', referenceFailure);
      if (permissionFailure) return decision(candidate, 'BLOCKED', permissionFailure);
      if (!publicOrAuthorized(candidate)) return decision(candidate, 'BLOCKED', 'VIEW_PERMISSION_UNKNOWN');
      if (candidate.playbackType !== 'OFFICIAL_PAGE') return decision(candidate, 'BLOCKED', 'ROUTE_TYPE_MISMATCH');
      return decision(candidate, 'ELIGIBLE', 'ROUTE_ELIGIBLE');
    }
    case 'AUTHORIZED_SOURCE': {
      if (referenceFailure) return decision(candidate, 'BLOCKED', referenceFailure);
      if (permissionFailure) return decision(candidate, 'BLOCKED', permissionFailure);
      if (candidate.viewingPermission !== 'AUTHORIZED') return decision(candidate, 'BLOCKED', 'VIEW_PERMISSION_DENIED');
      if (candidate.playbackType !== 'AUTHORIZED_STREAM') return decision(candidate, 'BLOCKED', 'ROUTE_TYPE_MISMATCH');
      if (candidate.rightsEvidence !== 'VERIFIED') return decision(candidate, 'BLOCKED', 'RIGHTS_EVIDENCE_REQUIRED');
      return decision(candidate, 'ELIGIBLE', 'ROUTE_ELIGIBLE');
    }
    case 'REPLAY': {
      if (candidate.replayType === 'AUTHORIZED_ON_DEMAND') {
        if (referenceFailure) return decision(candidate, 'BLOCKED', referenceFailure);
        if (permissionFailure) return decision(candidate, 'BLOCKED', permissionFailure);
        if (candidate.viewingPermission !== 'AUTHORIZED') return decision(candidate, 'BLOCKED', 'VIEW_PERMISSION_DENIED');
        if (candidate.playbackType !== 'AUTHORIZED_REPLAY') return decision(candidate, 'BLOCKED', 'ROUTE_TYPE_MISMATCH');
        if (candidate.rightsEvidence !== 'VERIFIED') return decision(candidate, 'BLOCKED', 'RIGHTS_EVIDENCE_REQUIRED');
        return decision(candidate, 'ELIGIBLE', 'ROUTE_ELIGIBLE');
      }
      if (candidate.replayType !== 'LOCAL_FILE') return decision(candidate, 'BLOCKED', 'ROUTE_TYPE_MISMATCH');
      if (candidate.localMedia !== 'AVAILABLE') return decision(candidate, 'BLOCKED', 'LOCAL_MEDIA_UNAVAILABLE');
      if (candidate.localSelection !== 'USER_SELECTED') return decision(candidate, 'BLOCKED', 'LOCAL_MEDIA_NOT_SELECTED');
      if (candidate.localViewingConfirmation === 'DENIED') return decision(candidate, 'BLOCKED', 'LOCAL_VIEW_PERMISSION_DENIED');
      if (candidate.localViewingConfirmation !== 'USER_CONFIRMED') return decision(candidate, 'BLOCKED', 'LOCAL_VIEW_PERMISSION_UNKNOWN');
      return decision(candidate, 'ELIGIBLE', 'ROUTE_ELIGIBLE');
    }
    case 'LIVE_SCORE': {
      if (referenceFailure) return decision(candidate, 'BLOCKED', referenceFailure);
      if (permissionFailure) return decision(candidate, 'BLOCKED', permissionFailure);
      if (!publicOrAuthorized(candidate) || candidate.liveScore !== 'LIVE_VERIFIED') {
        return decision(candidate, 'BLOCKED', 'LIVE_SCORE_UNVERIFIED');
      }
      return decision(candidate, 'SCORE_ONLY', 'ROUTE_ELIGIBLE');
    }
  }
}

export type WatchFailureSignal =
  | { source: 'HTTP'; status: number }
  | { source: 'NETWORK' }
  | { source: 'PROVIDER'; condition: 'REGION_RESTRICTED' | 'LOGIN_REQUIRED' | 'LINK_EXPIRED' | 'EMBED_DISABLED' | 'PLAYBACK_FAILED' | 'SOURCE_UNAVAILABLE' }
  | { source: 'LOCAL_MEDIA'; condition: 'FILE_MISSING' | 'MEDIA_DECODE_FAILED' }
  | { source: 'USER'; condition: 'CANCELLED' };

export type WatchFailureCode =
  | 'HTTP_FORBIDDEN'
  | 'HTTP_UNAUTHORIZED'
  | 'HTTP_NOT_FOUND'
  | 'HTTP_ERROR'
  | 'NETWORK_ERROR'
  | 'REGION_RESTRICTED'
  | 'LOGIN_REQUIRED'
  | 'LINK_EXPIRED'
  | 'EMBED_DISABLED'
  | 'PLAYBACK_FAILED'
  | 'SOURCE_UNAVAILABLE'
  | 'LOCAL_MEDIA_MISSING'
  | 'MEDIA_DECODE_FAILED'
  | 'USER_CANCELLED'
  | 'UNKNOWN';

export type WatchFailureAction =
  | 'SHOW_ELIGIBLE_ALTERNATIVES'
  | 'REVERIFY_SOURCE'
  | 'RETRY_OR_SHOW_ELIGIBLE_ALTERNATIVES'
  | 'OPEN_OFFICIAL_PAGE_IF_ELIGIBLE'
  | 'RESELECT_LOCAL_MEDIA'
  | 'NO_ACTION';

export interface WatchFailure {
  code: WatchFailureCode;
  action: WatchFailureAction;
  message: string;
}

/**
 * Classify only explicit transport/provider/media evidence. In particular,
 * HTTP 401/403 never imply login or region restrictions, and 404 never alone
 * proves that a link expired.
 */
export function classifyWatchFailure(input: unknown): WatchFailure {
  if (!input || typeof input !== 'object') return { code: 'UNKNOWN', action: 'SHOW_ELIGIBLE_ALTERNATIVES', message: '播放状态无法识别；请返回内容页选择其他已符合条件的方式。' };
  const signal = input as WatchFailureSignal;
  if (signal.source === 'HTTP' && typeof signal.status === 'number' && Number.isFinite(signal.status)) {
    if (signal.status === 403) return { code: 'HTTP_FORBIDDEN', action: 'SHOW_ELIGIBLE_ALTERNATIVES', message: '来源服务器拒绝访问；请使用仍符合权限条件的观看方式。' };
    if (signal.status === 401) return { code: 'HTTP_UNAUTHORIZED', action: 'SHOW_ELIGIBLE_ALTERNATIVES', message: '请求未获授权；登录要求需由来源平台明确确认。' };
    if (signal.status === 404) return { code: 'HTTP_NOT_FOUND', action: 'REVERIFY_SOURCE', message: '来源地址当前未找到；需重新核验，不能据此断定链接已过期。' };
    return { code: 'HTTP_ERROR', action: 'RETRY_OR_SHOW_ELIGIBLE_ALTERNATIVES', message: `来源请求失败（HTTP ${Number.isInteger(signal.status) ? signal.status : '未知'}）。` };
  }
  if (signal.source === 'NETWORK') return { code: 'NETWORK_ERROR', action: 'RETRY_OR_SHOW_ELIGIBLE_ALTERNATIVES', message: '网络连接失败；可以稍后重试或选择其他合规来源。' };
  if (signal.source === 'PROVIDER') {
    const messages: Record<Extract<WatchFailureSignal, { source: 'PROVIDER' }>['condition'], WatchFailure> = {
      REGION_RESTRICTED: { code: 'REGION_RESTRICTED', action: 'SHOW_ELIGIBLE_ALTERNATIVES', message: '来源平台明确报告地区限制；不尝试绕过限制。' },
      LOGIN_REQUIRED: { code: 'LOGIN_REQUIRED', action: 'SHOW_ELIGIBLE_ALTERNATIVES', message: '来源平台明确要求登录；请在平台允许的方式下观看。' },
      LINK_EXPIRED: { code: 'LINK_EXPIRED', action: 'REVERIFY_SOURCE', message: '来源平台明确报告链接失效；需重新核验官方入口。' },
      EMBED_DISABLED: { code: 'EMBED_DISABLED', action: 'OPEN_OFFICIAL_PAGE_IF_ELIGIBLE', message: '来源不允许嵌入；只有官方页面本身符合条件时才提供外链。' },
      PLAYBACK_FAILED: { code: 'PLAYBACK_FAILED', action: 'SHOW_ELIGIBLE_ALTERNATIVES', message: '来源播放器报告播放失败；可选择其他已符合条件的方式。' },
      SOURCE_UNAVAILABLE: { code: 'SOURCE_UNAVAILABLE', action: 'REVERIFY_SOURCE', message: '来源平台报告内容不可用；需重新核验来源状态。' },
    };
    return messages[signal.condition] ?? { code: 'UNKNOWN', action: 'SHOW_ELIGIBLE_ALTERNATIVES', message: '来源平台返回了无法识别的状态；请返回内容页选择其他已符合条件的方式。' };
  }
  if (signal.source === 'LOCAL_MEDIA') {
    if (signal.condition === 'FILE_MISSING') return { code: 'LOCAL_MEDIA_MISSING', action: 'RESELECT_LOCAL_MEDIA', message: '本地视频不可用；请重新选择本机文件。' };
    if (signal.condition === 'MEDIA_DECODE_FAILED') return { code: 'MEDIA_DECODE_FAILED', action: 'SHOW_ELIGIBLE_ALTERNATIVES', message: '浏览器无法解码本地视频；不能仅凭此结果判断具体编码或文件损坏。' };
  }
  if (signal.source === 'USER' && signal.condition === 'CANCELLED') return { code: 'USER_CANCELLED', action: 'NO_ACTION', message: '播放已由用户取消。' };
  return { code: 'UNKNOWN', action: 'SHOW_ELIGIBLE_ALTERNATIVES', message: '播放状态无法识别；请返回内容页选择其他已符合条件的方式。' };
}
