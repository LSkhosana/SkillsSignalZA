import { TRACK_OPTIONS } from '@/lib/constants';
import type { AssessmentSummaryItem, BandId } from '@/services/api';

const BAND_LABELS: Record<BandId, string> = {
  limited_application_evidence: 'Limited application evidence',
  foundation_visible: 'Foundation visible',
  developing_application_readiness: 'Developing application readiness',
  strong_application_evidence: 'Strong application evidence',
};

export function trackLabelForId(track: string): string {
  return TRACK_OPTIONS.find((option) => option.id === track)?.label ?? humanizeToken(track);
}

export function bandLabelForId(band: BandId | null): string | null {
  if (!band) {
    return null;
  }
  return BAND_LABELS[band];
}

export function formatCustomerDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function summaryScoreLine(item: AssessmentSummaryItem): string {
  if (item.final_score == null) {
    return 'Score not available yet';
  }
  return `${item.final_score} / 100`;
}

function humanizeToken(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}
