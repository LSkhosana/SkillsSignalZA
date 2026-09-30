import type {
  AnonymousAssessmentOutcome,
  AssessmentSummariesOutcome,
  AssessmentSummaryItem,
  PaymentCheckoutOutcome,
  PriorityActionRow,
  ReadinessPreview,
  ReadinessReport,
} from '@/services/api';

export const PREVIEW_FIXTURE: ReadinessPreview = {
  schema_version: 'readiness.preview.v1',
  report_version: '1.0.0',
  assessment_id: 'a-test-1',
  run_id: 'r-test-1',
  track: 'software_engineering',
  track_label: 'Software Engineering',
  final_score: 72,
  score_max: 100,
  band_id: 'developing_application_readiness',
  band_label: 'Developing application readiness',
  band_statement: 'The bundle shows real evidence, and the largest gaps are still open.',
  disclaimer: 'This measures submitted application evidence only. It does not predict hiring, interviews, or hidden ability.',
  strongest_area: {
    category_id: 'applied_build',
    label: 'Applied build',
    score: 18,
    max_points: 20,
    percentage: 90,
  },
  priority_gap: {
    criterion_id: 'se-evidence-depth',
    criterion_label: 'Evidence depth',
    category_id: 'evidence_quality',
    category_label: 'Evidence quality',
    point_gap: 4,
    gap_ratio: 0.5,
    current_anchor: 'partial',
    current_anchor_label: 'Partial',
    awarded_points: 4,
    max_points: 8,
  },
};

export const COMPLETED_ASSESSMENT: AnonymousAssessmentOutcome = {
  schema_version: 'anonymous.assessment.v1',
  state: 'COMPLETED',
  assessment_id: 'a-test-1',
  run_id: 'r-test-1',
  access_state: 'PREVIEW',
  claim_token: 'raw-claim-token-value',
  preview: PREVIEW_FIXTURE,
  error_code: null,
};

export const PAYMENT_INITIALIZED: PaymentCheckoutOutcome = {
  schema_version: 'payment.checkout.v1',
  state: 'PAYMENT_INITIALIZED',
  assessment_id: 'a-test-1',
  payment_id: 'pay_test_1',
  access_state: 'PREVIEW',
  amount_minor: 15900,
  currency: 'ZAR',
  provider: 'paystack',
  provider_reference: 'psk_test_1',
  authorization_url: 'https://checkout.paystack.com/test-session',
  error_code: null,
};

export const ALREADY_UNLOCKED: PaymentCheckoutOutcome = {
  schema_version: 'payment.checkout.v1',
  state: 'ALREADY_UNLOCKED',
  assessment_id: 'a-test-1',
  payment_id: 'pay_test_1',
  access_state: 'UNLOCKED',
  amount_minor: 15900,
  currency: 'ZAR',
  provider: 'paystack',
  provider_reference: 'psk_test_1',
  authorization_url: null,
  error_code: null,
};

export const REPORT_FIXTURE: ReadinessReport = {
  schema_version: 'readiness.report.v1',
  report_version: '1.0.0',
  assessment_id: 'a-test-1',
  run_id: 'r-test-1',
  contract_version: '1.2.0',
  rubric_version: 'V2',
  track: 'software_engineering',
  track_label: 'Software Engineering',
  assessed_at: '2026-09-11T08:00:00Z',
  benchmark: {
    scope_statement: 'This report evaluates demonstrated application-readiness evidence.',
    disclaimer: 'This measures submitted application evidence only. It does not predict hiring, interviews, or hidden ability.',
  },
  score_summary: {
    final_score: 72,
    score_max: 100,
    raw_total: 74,
    band_id: 'developing_application_readiness',
    band_label: 'Developing application readiness',
    band_statement: PREVIEW_FIXTURE.band_statement,
    open_points: 4,
    strongest_area: PREVIEW_FIXTURE.strongest_area,
    priority_gap: PREVIEW_FIXTURE.priority_gap,
    category_caps: [],
    overall_caps: [],
    applicable_overall_cap: 100,
  },
  category_breakdown: [
    {
      category_id: 'applied_build',
      label: 'Applied build',
      score: 18,
      max_points: 20,
      percentage: 90,
      pre_cap_score: 18,
    },
    {
      category_id: 'evidence_quality',
      label: 'Evidence quality',
      score: 12,
      max_points: 20,
      percentage: 60,
      pre_cap_score: 12,
    },
  ],
  strengths: [
    {
      criterion_id: 'se-build',
      criterion_label: 'Build evidence',
      category_id: 'applied_build',
      category_label: 'Applied build',
      awarded_points: 4,
      max_points: 4,
      anchor: 'strong',
      anchor_label: 'Strong',
      evidence_note: 'Shipped project evidence is visible.',
    },
    {
      criterion_id: 'se-evidence-depth',
      criterion_label: 'Evidence depth',
      category_id: 'evidence_quality',
      category_label: 'Evidence quality',
      awarded_points: 4,
      max_points: 8,
      anchor: 'partial',
      anchor_label: 'Partial',
      evidence_note: 'A walkthrough exists, but the production constraints are thin.',
    },
  ],
  material_gaps: [PREVIEW_FIXTURE.priority_gap!],
  priority_actions: [
    priorityAction(1, 'Add a production-shaped walkthrough of one shipped project.'),
    priorityAction(2, 'Name the trade-off that shaped the implementation.'),
    priorityAction(3, 'Publish tests that cover the main failure path.'),
    priorityAction(4, 'Document how a reviewer can run the project locally.'),
    priorityAction(5, 'Show the result against the original problem statement.'),
  ],
  project_recommendation: {
    status: 'RECOMMENDED',
    project_id: 'proj-1',
    title: 'Service health dashboard',
    scenario: 'Build a small service with observable health checks.',
    required_foundations: ['HTTP API', 'Tests'],
    required_outputs: ['Repository', 'README'],
    completion_checks: ['Health endpoint returns 200'],
    source_blueprint: 'catalogue',
    catalogue_version: '1.0.0',
  },
  criterion_breakdown: [
    {
      criterion_id: 'se-build',
      criterion_label: 'Build evidence',
      category_id: 'applied_build',
      category_label: 'Applied build',
      awarded_points: 4,
      max_points: 4,
      anchor: 'strong',
      anchor_label: 'Strong',
      evidence_note: 'Shipped project evidence is visible.',
      flags: [],
    },
    {
      criterion_id: 'se-evidence-depth',
      criterion_label: 'Evidence depth',
      category_id: 'evidence_quality',
      category_label: 'Evidence quality',
      awarded_points: 4,
      max_points: 8,
      anchor: 'partial',
      anchor_label: 'Partial',
      evidence_note: 'A walkthrough exists, but the production constraints are thin.',
      flags: [],
    },
    {
      criterion_id: 'se-local-run',
      criterion_label: 'Local run notes',
      category_id: 'applied_build',
      category_label: 'Applied build',
      awarded_points: 1,
      max_points: 2,
      anchor: 'named_only',
      anchor_label: 'Named only',
      evidence_note: 'Only the criterion table quotes this line.',
      flags: [],
    },
  ],
};

function priorityAction(order: number, instruction: string): PriorityActionRow {
  return {
    priority_order: order,
    action_id: `action-${order}`,
    criterion_id: 'se-evidence-depth',
    criterion_label: 'Evidence depth',
    evidence_lead:
      'A walkthrough exists, but the production constraints are thin. 4 points are still open.',
    current_anchor: 'partial',
    current_anchor_label: 'Partial',
    target_anchor: 'strong',
    target_anchor_label: 'Strong',
    candidate_instruction: instruction,
    required_output: 'A public write-up with decisions and constraints.',
    completion_check: 'The write-up names the problem, trade-off, and result.',
    action_type: 'evidence',
  };
}

export const UNLOCKED_SUMMARY: AssessmentSummaryItem = {
  assessment_id: 'a-test-1',
  track: 'software_engineering',
  final_score: 72,
  band: 'developing_application_readiness',
  access_state: 'UNLOCKED',
  assessed_at: '2026-09-11T08:00:00Z',
  unlocked_at: '2026-09-12T09:00:00Z',
};

export const PREVIEW_SUMMARY: AssessmentSummaryItem = {
  assessment_id: 'a-test-2',
  track: 'data_analytics',
  final_score: 59,
  band: 'foundation_visible',
  access_state: 'PREVIEW',
  assessed_at: '2026-09-10T08:00:00Z',
  unlocked_at: null,
};

export const LISTED_SUMMARIES: AssessmentSummariesOutcome = {
  schema_version: 'assessment.summaries.v1',
  state: 'LISTED',
  items: [UNLOCKED_SUMMARY, PREVIEW_SUMMARY],
  limit: 50,
  offset: 0,
  has_more: false,
  error_code: null,
};

export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export function headerMap(init?: RequestInit): Record<string, string> {
  const headers = init?.headers;
  if (!headers) {
    return {};
  }
  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return { ...(headers as Record<string, string>) };
}

export function formField(body: FormData, name: string): string | null {
  if (typeof body.get === 'function') {
    const value = body.get(name);
    return value == null ? null : String(value);
  }
  const parts = (body as { getParts?: () => { fieldName?: string; string?: string }[] }).getParts?.() ?? [];
  const part = parts.find((item) => item.fieldName === name);
  return part?.string ?? null;
}
