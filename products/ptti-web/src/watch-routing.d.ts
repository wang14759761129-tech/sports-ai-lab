declare module '@ptti/watch-routing' {
  export interface WatchRouteDecision {
    contract: 'ptti.watch-routing/0.1';
    mode: 'OFFICIAL_EMBED' | 'OFFICIAL_PAGE' | 'AUTHORIZED_SOURCE' | 'REPLAY' | 'LIVE_SCORE';
    state: 'ELIGIBLE' | 'SCORE_ONLY' | 'BLOCKED';
    playbackEvidence: 'VERIFIED' | 'NOT_TESTED' | 'FAILED';
    reason: string;
  }
  export function evaluateWatchRoute(input: unknown): WatchRouteDecision | null;
}
