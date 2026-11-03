export type Discipline = 'MS' | 'WS' | 'MD' | 'WD' | 'XD';

export type SourceStatus = 'official-listing-found' | 'no-verified-route';

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
  platformUrl: string | null;
  videoOriginalUrl: string | null;
  sourceStatus: SourceStatus;
  playbackTested: boolean;
  regionRestriction: string;
  embedAllowed: boolean | null;
  lastVerifiedAt: string;
  sourceEvidence: string[];
  note: string;
}

export interface PulseItem {
  id: string;
  category: 'Official highlight' | 'Player feature' | 'Event discussion';
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
  statusClarity: number;
  friction: string;
  returnIntent: 'yes' | 'unsure' | 'no';
}
