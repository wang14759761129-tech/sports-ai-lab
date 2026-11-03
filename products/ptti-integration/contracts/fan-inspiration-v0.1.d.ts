export type VideoCategory =
  | 'FULL_MATCH_TITLE_CLAIM'
  | 'EVENT_HIGHLIGHTS_TITLE_CLAIM'
  | 'SEASON_HIGHLIGHTS_TITLE_CLAIM'
  | 'MATCH_SPECIFIC_TYPE_UNKNOWN'
  | 'EVENT_LEVEL_TYPE_UNKNOWN';

export type VerificationStatus =
  | 'VERIFIED_METADATA_BASELINE'
  | 'CURRENT_SEARCH_METADATA_SURFACED'
  | 'NOT_TESTED'
  | 'UNVERIFIED';

export interface VideoVerification {
  publisher_identity: 'VERIFIED' | 'UNKNOWN';
  source_identity: 'VERIFIED' | 'UNKNOWN';
  match_link: 'HUMAN_VERIFIED' | 'TITLE_ASSOCIATION_VISUAL_NOT_TESTED' | 'UNKNOWN' | 'NOT_APPLICABLE';
  metadata_status: VerificationStatus;
  metadata_checked_at: string | null;
  official_page_open: 'NOT_TESTED' | 'PARTIAL_METADATA_ONLY';
  external_system_browser_open: 'NOT_TESTED';
  video_started: 'NOT_TESTED';
  complete_watch: 'UNVERIFIED';
  desktop_native_playback: 'NOT_TESTED';
  vision_analysis: 'NOT_TESTED';
  territory: 'UNKNOWN';
}

export interface VideoRights {
  public_listing: 'ALLOWED' | 'ALLOWED_EXTERNAL_LINK_ONLY';
  external_viewing: 'ALLOWED' | 'ALLOWED_WITHIN_PLATFORM_LINK_SHARING_SCOPE';
  embed: 'UNKNOWN_NOT_GRANTED';
  thumbnail_display: 'NOT_ALLOWED' | 'NOT_GRANTED_PENDING_APPROVAL';
  download: 'NOT_GRANTED';
  local_analysis: 'NOT_GRANTED';
  redistribution: 'NOT_GRANTED';
}

export interface FanVideoContent {
  source_id: string;
  platform: 'YOUTUBE';
  original_url: string;
  original_title: string;
  published_at: string | null;
  publisher: 'World Table Tennis';
  publisher_url: string;
  athlete_ids: string[];
  athlete_names: string[];
  athlete_association_status: 'MATCH_LINKED' | 'UNASSIGNED_EVENT_LEVEL' | 'UNMAPPED_TITLE_NAMES' | 'UNKNOWN';
  event_id: string | null;
  event_name: string | null;
  event_year: number | null;
  match_id: string | null;
  video_category: VideoCategory;
  full_match_completeness: 'UNVERIFIED';
  verification: VideoVerification;
  rights: VideoRights;
}

export interface InternationalReaction {
  reaction_id: string;
  related_match_id: string | null;
  content_kind: 'SINGLE_MEDIA_REPORT';
  publisher: string;
  source_url: string;
  source_title: string;
  published_at: string;
  language: string;
  summary_zh: string;
  credibility: {
    source_class: 'ESTABLISHED_NATIONAL_NEWSROOM';
    confidence_scope: 'HIGH_FOR_ATTRIBUTING_THIS_ARTICLE_ONLY';
    audience_representativeness: 'NOT_CLAIMED';
  };
  rights: {
    public_listing: 'FACTUAL_SUMMARY_AND_OUTBOUND_LINK_ONLY';
    article_republication: 'NOT_GRANTED';
    image_reuse: 'NOT_GRANTED';
  };
}

export interface GearItemEvidence {
  category: 'JERSEY' | 'SHOES' | 'BLADE' | 'RUBBER';
  brand: null;
  model: null;
  status: 'UNKNOWN';
}

export interface MatchGearDossier {
  match_id: string;
  participants: Array<{
    athlete_id: string | null;
    athlete_name: string;
    match_specific_status: 'NOT_VERIFIED';
    items: GearItemEvidence[];
  }>;
  evidence_status: 'NOT_VERIFIED_FOR_SPECIFIC_MATCH';
  public_note: string;
}

export interface WatchRoutePolicy {
  mode: 'OFFICIAL_EMBED' | 'OFFICIAL_PAGE' | 'AUTHORIZED_SOURCE' | 'REPLAY' | 'LIVE_SCORE';
  priority: 1 | 2 | 3 | 4 | 5;
  state:
    | 'BLOCKED_NO_EXPLICIT_EMBED_PERMISSION'
    | 'OUTBOUND_LINKS_REGISTERED_PLAYBACK_NOT_TESTED'
    | 'NO_AUTHORIZED_SOURCE_REGISTERED'
    | 'OFFICIAL_REPLAY_LINKS_NOT_PLAYBACK_VERIFIED'
    | 'NO_LIVE_SCORE_VERIFIED';
  source_ids: string[];
  playback_evidence: 'NOT_TESTED';
  fallback_behavior: string;
}

export interface FanInspirationV01 {
  contract_version: 'ptti.fan-inspiration/0.1';
  generated_at: string;
  view: 'STRICT_PUBLIC_METADATA_LINKS_ONLY';
  input_identity: {
    base_contract: 'ptti.match-library-index/0.1';
    base_sha256: string;
    goal17_delta_contract: 'ptti.goal17.1-match-video-additions/0.1';
    goal17_delta_sha256: string;
    goal22_supplement_sha256: string;
  };
  clips: FanVideoContent[];
  match_watch_sources: FanVideoContent[];
  international_reactions: InternationalReaction[];
  gear_dossiers: MatchGearDossier[];
  watch_routes: WatchRoutePolicy[];
  notice: string;
}
