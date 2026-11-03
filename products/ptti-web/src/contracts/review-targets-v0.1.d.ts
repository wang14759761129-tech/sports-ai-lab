import type { QuickAnnotationStatsV01, QuickAnnotationMetricV01 } from './quick-annotation-stats-v0.1';
export type ReviewRole = 'player' | 'opponent';
export type ObservedReviewStage = 'END_AFTER_1_2_CONTACTS' | 'END_AFTER_3_4_CONTACTS' | 'END_AFTER_5_PLUS_CONTACTS';
export type ReviewEvidence = 'SIMULATED_ONLY' | 'REVIEW_REQUIRED';
export type ReviewSampleStatus = 'NOT_ESTIMABLE' | 'INSUFFICIENT_SAMPLE' | 'DESCRIPTIVE_ONLY';
export interface ReviewCount {
  won_count: number; lost_count: number; denominator: number; sample_count: number;
  unknown_count: number; excluded_count: number;
  point_ids: { valid: string[]; won: string[]; lost: string[]; unknown: string[]; excluded: string[] };
  computation_rule: string; evidence_status: ReviewEvidence; sample_status: ReviewSampleStatus;
}
export interface ReviewTarget {
  target_id: string; subject_role: ReviewRole; observed_rally_stage: ObservedReviewStage;
  lost_count: number; denominator: number; unknown_count: number; point_ids: string[];
  evidence_status: ReviewEvidence; sample_status: ReviewSampleStatus;
  playback_eligibility: 'NOT_EVALUATED_CURRENT_SESSION';
}
export interface ReviewTargetsV01 {
  contract_version: 'ptti.review-targets/0.1';
  input_contract_version: 'ptti.quick-annotation/0.1' | 'ptti.quick-annotation/0.2';
  statistics_contract_version: 'ptti.quick-annotation-stats/0.1';
  canonical_input_sha256: string; dataset: QuickAnnotationStatsV01['dataset'];
  evidence_status: ReviewEvidence; display_caution_threshold: number; threshold_is_significance_test: false;
  sample: QuickAnnotationStatsV01['sample']; time_range_coverage: QuickAnnotationMetricV01;
  unknown_stage_count: number; unknown_server_count: number;
  athletes: Array<{ role: ReviewRole; identity_status: 'INPUT_ROLE_ONLY'; score: ReviewCount;
    service: ReviewCount; observed_stages: Record<ObservedReviewStage, ReviewCount> }>;
  review_targets: ReviewTarget[];
  observations: Array<{ target_id: string; point_ids: string[]; text_zh: string }>;
  limitations: string[];
}
