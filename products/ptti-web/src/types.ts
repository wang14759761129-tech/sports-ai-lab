export type Discipline = 'MS' | 'WS' | 'MD' | 'WD' | 'XD';

export type SourceStatus = 'official-listing-found' | 'no-verified-route';
export type MatchRouteType = 'event-page' | 'video-page' | 'source-only';
export type PlaybackStatus = 'PLAYBACK_PASS' | 'PLAYBACK_FAIL' | 'RESTRICTED' | 'NOT_TESTED';
export type PulseTopic = 'highlight' | 'player' | 'event';
export type FeedbackIssue = 'none' | 'find-match' | 'official-link' | 'unclear-page' | 'mobile-display' | 'other';

export interface PlaybackEvidence {
  testedAt: string;
  finalUrl: string;
  pageTitle: string;
  publisher: string;
  timeAtFirstObservationSeconds: number;
  timeAtFinalObservationSeconds: number;
  visualFramesChanged: boolean;
  loginPromptSeen: boolean;
  regionPromptSeen: boolean;
  verificationPromptSeen: boolean;
  playerUnmuted: boolean;
  playerVolumePercent: number;
  audibleOutputConfirmed: boolean;
  territory: string;
}

export interface MatchRecord {
  id: string;
  event: string;
  eventCategory: string;
  eventYear: number;
  discipline: Discipline;
  round: string;
  players: string[];
  result?: string;
  platform: string;
  routeType: MatchRouteType;
  platformUrl: string | null;
  videoOriginalUrl: string | null;
  sourceStatus: SourceStatus;
  playbackTested: boolean;
  playbackStatus: PlaybackStatus;
  playbackEvidence?: PlaybackEvidence;
  regionRestriction: string;
  embedAllowed: boolean | null;
  lastVerifiedAt: string;
  sourceEvidence: string[];
  note: string;
}

export interface PulseItem {
  id: string;
  category: 'Official highlight' | 'Player feature' | 'Event discussion';
  topic: PulseTopic;
  title: string;
  publisher: string;
  platform: string;
  url: string;
  evidenceUrl: string;
  format: 'video' | 'article';
  summary: string;
  publishedAt?: string;
  verifiedAt: string;
  playbackTested: boolean;
}

export interface StarProfile {
  id: string;
  name: string;
  countryCode: string;
  intro: string;
  representativeEvent: string;
  publicFact: string;
  sourceUrl: string;
  relatedMatchId?: string;
  newsTitle?: string;
  newsUrl?: string;
  socialUrl?: string;
  socialStatus: string;
}

export interface FeedbackEntry {
  id: string;
  createdAt: string;
  role: 'fan' | 'athlete' | 'coach' | 'other';
  foundMatch: 'yes' | 'partly' | 'no';
  clickOutcome: 'opened' | 'blocked' | 'not-tried';
  issueCategory?: FeedbackIssue;
  statusClarity: number;
  friction: string;
  returnIntent: 'yes' | 'unsure' | 'no';
}
