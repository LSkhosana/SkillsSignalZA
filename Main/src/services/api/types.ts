import type { DeclaredLinkType, TrackId } from '@/lib/constants';

export type CandidateLinkInput = {
  submitted_url: string;
  declared_type: DeclaredLinkType;
};

export type StrongestArea = {
  category_id: string;
  label: string;
  score: number;
  max_points: number;
  percentage: number;
};

export type PriorityGap = {
  criterion_id: string;
  criterion_label: string;
  category_id: string;
  category_label: string;
  point_gap: number;
  gap_ratio: number;
  current_anchor: string;
  current_anchor_label: string;
  awarded_points: number;
  max_points: number;
};

export type ReadinessPreview = {
  schema_version: 'readiness.preview.v1';
  report_version: string;
  assessment_id: string;
  run_id: string;
  track: TrackId;
  track_label: string;
  final_score: number;
  score_max: 100;
  band_id: string;
  band_label: string;
  strongest_area: StrongestArea;
  priority_gap: PriorityGap | null;
};

export type AnonymousAssessmentOutcome = {
  schema_version: 'anonymous.assessment.v1';
  state: 'COMPLETED' | 'REVIEW_REQUIRED' | 'NOT_SCORABLE' | 'FAILED';
  assessment_id: string;
  run_id: string;
  access_state: 'PREVIEW' | null;
  claim_token: string | null;
  preview: ReadinessPreview | null;
  error_code: string | null;
};

export type AssessmentClaimOutcome = {
  schema_version: 'assessment.claim.v1';
  state: 'CLAIMED' | 'FAILED';
  assessment_id: string;
  access_state: 'PREVIEW' | null;
  claimed_at: string | null;
  error_code: string | null;
};

export type PaymentCheckoutOutcome = {
  schema_version: 'payment.checkout.v1';
  state: 'PAYMENT_INITIALIZED' | 'ALREADY_UNLOCKED' | 'FAILED';
  assessment_id: string;
  payment_id: string | null;
  access_state: 'PREVIEW' | 'UNLOCKED' | null;
  amount_minor: number | null;
  currency: string | null;
  provider: string | null;
  provider_reference: string | null;
  authorization_url: string | null;
  error_code: string | null;
};

export type AssessmentReportError = {
  schema_version: 'assessment.report.v1';
  state: 'FAILED';
  assessment_id: string;
  error_code: string;
};

export type CategoryBreakdownRow = {
  category_id: string;
  label: string;
  score: number;
  max_points: number;
  percentage: number;
  pre_cap_score: number;
};

export type StrengthRow = {
  criterion_id: string;
  criterion_label: string;
  category_id: string;
  category_label: string;
  awarded_points: number;
  max_points: number;
  anchor: string;
  anchor_label: string;
  evidence_note: string;
};

export type MaterialGapRow = PriorityGap;

export type PriorityActionRow = {
  priority_order: number;
  action_id: string;
  criterion_id: string;
  criterion_label: string;
  current_anchor: string;
  current_anchor_label: string;
  target_anchor: string;
  target_anchor_label: string;
  candidate_instruction: string;
  required_output: string;
  completion_check: string;
  action_type: string;
};

export type ProjectRecommendation =
  | null
  | { status: 'REVIEW_REQUIRED' }
  | {
      status: 'RECOMMENDED';
      project_id: string;
      title: string;
      scenario: string;
      required_foundations: string[];
      required_outputs: string[];
      completion_checks: string[];
      data_requirement?: string;
      source_blueprint: string;
      catalogue_version: string;
    };

export type CriterionBreakdownRow = {
  criterion_id: string;
  criterion_label: string;
  category_id: string;
  category_label: string;
  awarded_points: number;
  max_points: number;
  anchor: string;
  anchor_label: string;
  evidence_note: string;
  flags: string[];
};

export type ReadinessReport = {
  schema_version: 'readiness.report.v1';
  report_version: string;
  assessment_id: string;
  run_id: string;
  contract_version: string;
  rubric_version: string;
  track: TrackId;
  track_label: string;
  assessed_at: string;
  benchmark: {
    scope_statement: string;
    disclaimer: string;
  };
  score_summary: {
    final_score: number;
    score_max: 100;
    raw_total: number;
    band_id: string;
    band_label: string;
    strongest_area: StrongestArea;
    priority_gap: PriorityGap | null;
    category_caps: {
      rule_id: string;
      rule_label: string;
      category_id: string;
      category_label: string;
      cap: number;
    }[];
    overall_caps: {
      rule_id: string;
      rule_label: string;
      cap: number;
    }[];
    applicable_overall_cap: number;
  };
  category_breakdown: CategoryBreakdownRow[];
  strengths: StrengthRow[];
  material_gaps: MaterialGapRow[];
  priority_actions: PriorityActionRow[];
  project_recommendation: ProjectRecommendation;
  criterion_breakdown: CriterionBreakdownRow[];
};

export type PickedCvDocument = {
  uri: string;
  name: string;
  mimeType: string;
  size: number | null;
};

export const PAID_REPORT_SECTION_KEYS = [
  'category_breakdown',
  'strengths',
  'material_gaps',
  'priority_actions',
  'project_recommendation',
  'criterion_breakdown',
  'benchmark',
] as const;
