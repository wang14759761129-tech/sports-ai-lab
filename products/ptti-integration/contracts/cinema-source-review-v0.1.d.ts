/** Internal-only review view. This contract is not a public content feed. */
export type ReviewPermission = "ALLOWED" | "NOT_ALLOWED" | "NOT_GRANTED" | "UNKNOWN";
export type MatchDiscipline = "MS" | "WS" | "MD" | "WD" | "XD";
export type MatchDateReview = {
  value: string | null;
  status: "OFFICIAL_REPORT_DATE" | "SECONDARY_CATALOG_ONLY" | "UNKNOWN";
  local_start_time: null;
};
export type ReviewEvidenceSource = {
  role: "OFFICIAL_MATCH_RESULT" | "OFFICIAL_EVENT_INFO" | "SECONDARY_STREAMING_CATALOG";
  url: string;
  claims: string[];
};
export type CinemaSourceReview = {
  source_id: string;
  catalog_record_id: string;
  video_id: string;
  platform: "YOUTUBE";
  original_source_url: string;
  watch_entry: "OPEN_OFFICIAL_PLATFORM_URL";
  publisher_metadata: {
    method: "YOUTUBE_OEMBED_SINGLE_LOOKUP";
    checked_at: string;
    title: string;
    author_name: string;
    author_url: string;
    status: "MATCHES_SNAPSHOT_METADATA_AFFILIATION_AND_RIGHTS_SCOPE_NOT_PROVEN";
  };
  match_claim: {
    event_name: string;
    event_year: number;
    discipline: MatchDiscipline;
    round: string;
    participants: string[];
    status: string;
    match_date: MatchDateReview;
    event_window: { start: string; end: string; status: "OFFICIAL_EVENT_INFO" } | null;
    evidence_sources: ReviewEvidenceSource[];
    official_source_references_video_id: false;
  };
  match_link: {
    canonical_match_id: null;
    status: "UNKNOWN";
    unlinked_review_candidate_match_id: string | null;
    reason: string;
    join_policy: "EXACT_EVIDENCE_REQUIRED_NO_AUTOMATIC_JOIN_BY_TITLE_EVENT_OR_PLAYER_NAME";
  };
  watch_status: {
    official_page_request: "HTTP_200_PAGE_ONLY" | "HTTP_NON_200_REVIEW_REQUIRED";
    page_checked_at: string;
    external_visual_video_playback: "NOT_TESTED";
    external_viewing_rights: ReviewPermission;
    territory_status: string;
    login_or_region_check: "NOT_TESTED";
    in_app_embedding_permission: ReviewPermission;
    latest_recorded_embed_technical_status: string;
    in_app_entry: "EXTERNAL_ONLY_PERMISSION_UNVERIFIED";
    unavailability_or_limit_reason: string;
  };
  content_claim: {
    publisher_title_claim: "FULL_MATCH" | "HIGHLIGHTS" | "SESSION" | "CLIP" | "UNKNOWN";
    completeness: "VERIFIED" | "UNVERIFIED";
    completeness_status: "UNVERIFIED_TITLE_IS_NOT_COMPLETENESS_EVIDENCE";
  };
  rights: Record<"public_listing" | "external_viewing" | "thumbnail_display" | "embedding" | "local_analysis" | "redistribution", ReviewPermission>;
  thumbnail: { url: null; display_permission: ReviewPermission; presentation: "PTTI_BRAND_PLACEHOLDER_ONLY" };
  audience: "INTERNAL_REVIEW_ONLY";
  next_evidence_needed: string[];
};
export type CinemaSourceReviewDocument = {
  contract_version: "ptti.cinema-source-review/0.1";
  source_contract_version: "ptti.match-library-index/0.1";
  input_contract_version: "ptti.cinema-source-review-input/0.1";
  audience: "INTERNAL_REVIEW_ONLY";
  generated_at: string;
  catalog_snapshot: { unique_video_sources: number; registered_match_records: number; canonical_video_match_links: number; strict_public_video_source_count: 0 };
  summary: { selected_sources: number; official_pages_http_200: number; external_visual_playback_pass: 0; canonical_match_links: 0; public_projection_fallback: false };
  featured_sources: CinemaSourceReview[];
  notice: string;
};
