export type QuickAnnotationEvidenceStatus = "REVIEW_REQUIRED" | "SIMULATED_ONLY";
export type QuickAnnotationMetricStatus = "NOT_ESTIMABLE" | "INSUFFICIENT_SAMPLE" | "DESCRIPTIVE_ONLY";

export interface QuickAnnotationMetricV01<Numerator = number | Record<string, number>> {
  numerator: Numerator;
  denominator: number;
  sample_count: number;
  missing_count: number;
  value: number | null;
  computation_rule: string;
  evidence_status: QuickAnnotationEvidenceStatus | "RANGE_CHECKED_UNBOUND" | "UNBOUND_OR_UNKNOWN" | "NOT_ESTABLISHED_UNBOUND";
  sample_status: QuickAnnotationMetricStatus;
  display_caution_threshold: number;
  threshold_is_significance_test: false;
  [extra: string]: unknown;
}

export interface QuickAnnotationStatsV01 {
  contract_version: "ptti.quick-annotation-stats/0.1";
  input_contract_version: "ptti.quick-annotation/0.1" | "ptti.quick-annotation/0.2";
  draft_status: "LIGHT_ANNOTATION_DRAFT" | "SIMULATED_ONLY";
  evidence_status: QuickAnnotationEvidenceStatus;
  dataset: {
    dataset_id: string;
    dataset_class: "HUMAN_QUICK_DRAFT" | "SIMULATED_ONLY";
    match_id: string;
    match_link_status: string;
    source_id: string | null;
    source_link_status: string;
    rights_status: "UNKNOWN";
    source_video_sha256: string | null;
    timeline_id: string | null;
    pts: number | null;
    time_base: string | null;
    vision_status: "NOT_TESTED";
  };
  sample: {
    point_count: number;
    protocol_sequence_valid: boolean;
    score_known_count: number;
    score_unknown_count: number;
    score_before_trace_known_count: number;
    game_count: number;
    game_counts: Record<string, { point_count: number; known_winner_count: number; player_wins: number; opponent_wins: number }>;
  };
  metrics: {
    score_record_coverage: QuickAnnotationMetricV01;
    recorded_point_wins: QuickAnnotationMetricV01<Record<string, number>>;
    time_range_coverage: QuickAnnotationMetricV01;
    timeline_bound_review_coverage: QuickAnnotationMetricV01;
    server_point_win_rate: QuickAnnotationMetricV01;
    receiver_point_win_rate: QuickAnnotationMetricV01;
    tactical_fields: Record<string, QuickAnnotationMetricV01>;
    third_ball_attack_rate: QuickAnnotationMetricV01;
    third_ball_immediate_success: QuickAnnotationMetricV01;
    third_ball_server_point_conversion: QuickAnnotationMetricV01;
    key_point_player_win_rate: QuickAnnotationMetricV01;
  };
  rally_stage_distribution: {
    contract_version: "ptti.quick-annotation-stage-stats/0.1";
    status: "NOT_AVAILABLE_INPUT_V0_1" | "USER_OBSERVED_DRAFT";
    numerator: Record<string, number>;
    denominator: number;
    sample_count: number;
    missing_count: number;
    computation_rule: string;
    evidence_status: string;
    sample_status: QuickAnnotationMetricStatus;
    display_caution_threshold: number;
    threshold_is_significance_test: false;
  };
  review_candidates: Array<{
    point_id: string;
    start_ms: number;
    end_ms: number;
    observed_labels: Record<string, string | number>;
    observed_rally_stage?: "END_AFTER_1_2_CONTACTS" | "END_AFTER_3_4_CONTACTS" | "END_AFTER_5_PLUS_CONTACTS" | "UNKNOWN";
    status: "REVIEW_CANDIDATE_NOT_VIDEO_BOUND";
    limitation: string;
  }>;
  limitations: string[];
  automatic_formal_report_promotion: false;
  automatic_vision_promotion: false;
}
