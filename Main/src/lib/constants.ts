export const TRACKS = ['software_engineering', 'data_analytics'] as const;

export type TrackId = (typeof TRACKS)[number];

export const TRACK_OPTIONS: { id: TrackId; label: string; description: string }[] = [
  {
    id: 'software_engineering',
    label: 'Software Engineering',
    description: 'Application-readiness evidence for software engineering roles.',
  },
  {
    id: 'data_analytics',
    label: 'Data Analytics',
    description: 'Application-readiness evidence for data analytics roles.',
  },
];

export const DECLARED_LINK_TYPES = [
  'repository',
  'portfolio',
  'project',
  'deployed_project',
  'kaggle',
  'dashboard',
  'other_professional',
] as const;

export type DeclaredLinkType = (typeof DECLARED_LINK_TYPES)[number];

export const LINK_TYPE_LABELS: Record<DeclaredLinkType, string> = {
  repository: 'Repository',
  portfolio: 'Portfolio',
  project: 'Project',
  deployed_project: 'Deployed project',
  kaggle: 'Kaggle',
  dashboard: 'Dashboard',
  other_professional: 'Other professional',
};

export const MAX_LINKS = 5;
export const MAX_CV_BYTES = 10 * 1024 * 1024;
export const PDF_MEDIA_TYPE = 'application/pdf';
export const DOCX_MEDIA_TYPE =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
export const SUPPORTED_CV_MEDIA_TYPES = [PDF_MEDIA_TYPE, DOCX_MEDIA_TYPE] as const;

export const REPORT_PRICE_COPY = 'R159';
export const ASSESSMENTS_PATH = '/api/v1/assessments';

export const REPORT_POLL_INTERVAL_MS = 3000;
export const REPORT_POLL_MAX_ATTEMPTS = 20;
