import type { MatchRecord } from './types';

export type WatchFilter = 'all' | 'verified-video' | 'event-page' | 'source-only' | 'unverified';

export interface MatchFilters {
  query?: string;
  discipline?: string;
  event?: string;
  platform?: string;
  watchFilter?: WatchFilter;
}

export type MatchDestination =
  | { type: 'video-page'; url: string }
  | { type: 'event-page'; url: string }
  | { type: 'source-only'; url: string }
  | null;

export function getMatchDestination(match: MatchRecord): MatchDestination;
export function hasVerifiedVisualPlayback(match: MatchRecord): boolean;
export function filterMatchRecords(matches: MatchRecord[], filters?: MatchFilters): MatchRecord[];
export function getWatchFilterCounts(matches: MatchRecord[], filters?: Omit<MatchFilters, 'watchFilter'>): Record<WatchFilter, number>;
