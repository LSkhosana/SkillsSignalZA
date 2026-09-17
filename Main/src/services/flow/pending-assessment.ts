import AsyncStorage from '@react-native-async-storage/async-storage';

import type { ReadinessPreview } from '@/services/api';

export const PENDING_ASSESSMENT_STORAGE_KEY = 'ssza.pending.assessment.v1';

export type PendingAssessment = {
  assessment_id: string;
  preview: ReadinessPreview;
  claimed: boolean;
};

export type KeyValueStorage = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
  removeItem: (key: string) => Promise<void>;
};

let storage: KeyValueStorage = AsyncStorage;

export function setPendingAssessmentStorageForTests(next: KeyValueStorage | null): void {
  storage = next ?? AsyncStorage;
}

function isPreview(value: unknown): value is ReadinessPreview {
  return Boolean(
    value &&
      typeof value === 'object' &&
      (value as { schema_version?: unknown }).schema_version === 'readiness.preview.v1' &&
      typeof (value as { assessment_id?: unknown }).assessment_id === 'string' &&
      typeof (value as { final_score?: unknown }).final_score === 'number',
  );
}

export function parsePendingAssessment(raw: string | null): PendingAssessment | null {
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') {
      return null;
    }
    const record = parsed as Record<string, unknown>;
    if (typeof record.assessment_id !== 'string' || !record.assessment_id) {
      return null;
    }
    if (!isPreview(record.preview)) {
      return null;
    }
    if ('claim_token' in record) {
      return null;
    }
    return {
      assessment_id: record.assessment_id,
      preview: record.preview,
      claimed: record.claimed === true,
    };
  } catch {
    return null;
  }
}

export async function savePendingAssessment(pending: PendingAssessment): Promise<void> {
  const payload: PendingAssessment = {
    assessment_id: pending.assessment_id,
    preview: pending.preview,
    claimed: pending.claimed,
  };
  await storage.setItem(PENDING_ASSESSMENT_STORAGE_KEY, JSON.stringify(payload));
}

export async function loadPendingAssessment(): Promise<PendingAssessment | null> {
  const raw = await storage.getItem(PENDING_ASSESSMENT_STORAGE_KEY);
  return parsePendingAssessment(raw);
}

export async function markPendingAssessmentClaimed(assessmentId: string): Promise<void> {
  const current = await loadPendingAssessment();
  if (!current || current.assessment_id !== assessmentId) {
    return;
  }
  await savePendingAssessment({ ...current, claimed: true });
}

export async function clearPendingAssessment(): Promise<void> {
  await storage.removeItem(PENDING_ASSESSMENT_STORAGE_KEY);
}
