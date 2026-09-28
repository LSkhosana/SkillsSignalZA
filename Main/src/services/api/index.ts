export { apiClient, createApiClient, hasApiBaseUrl } from './client';
export type {
  ApiClient,
  ApiFailure,
  ApiRequestOptions,
  ApiResult,
  ApiSuccess,
  CreateApiClientOptions,
  FetchLike,
  HttpMethod,
} from './client';
export { ApiError, isApiError, toApiError } from './errors';
export type { ApiErrorPayload } from './errors';
export { customerMessageForCode, customerMessageFromError, isAuthError } from './customer-errors';
export { getHealth, HEALTH_PATH } from './health';
export type { HealthResponse } from './health';
export {
  buildAssessmentFormData,
  claimAssessment,
  getReport,
  initializePayment,
  isAssessmentSummariesOutcome,
  isReadinessReport,
  listOwnedAssessments,
  submitAssessment,
} from './assessments';
export type { AssessmentRequestOptions, SubmitAssessmentInput } from './assessments';
export type {
  AnonymousAssessmentOutcome,
  AssessmentClaimOutcome,
  AssessmentReportError,
  AssessmentSummariesOutcome,
  AssessmentSummaryItem,
  BandId,
  CandidateLinkInput,
  CategoryBreakdownRow,
  CriterionBreakdownRow,
  MaterialGapRow,
  PaymentCheckoutOutcome,
  PickedCvDocument,
  PriorityActionRow,
  PriorityGap,
  ProjectRecommendation,
  ReadinessPreview,
  ReadinessReport,
  StrengthRow,
  StrongestArea,
} from './types';
export { BAND_IDS, PAID_REPORT_SECTION_KEYS } from './types';
