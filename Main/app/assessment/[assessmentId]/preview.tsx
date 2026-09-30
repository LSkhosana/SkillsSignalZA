import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';

import { PreviewSummary } from '@/components/preview-summary';
import { Button } from '@/components/system/button';
import { PageState } from '@/components/system/feedback';
import { PageShell } from '@/components/system/page-shell';
import { PreviewSkeleton } from '@/components/system/skeleton';
import { REPORT_PRICE_COPY } from '@/lib/constants';
import { toHref } from '@/lib/href';
import type { ReadinessPreview } from '@/services/api';
import { useAuth } from '@/services/auth/provider';
import { loadPendingAssessment } from '@/services/flow';

export default function PreviewScreen() {
  const router = useRouter();
  const auth = useAuth();
  const params = useLocalSearchParams<{ assessmentId?: string | string[] }>();
  const assessmentId = Array.isArray(params.assessmentId) ? params.assessmentId[0] : params.assessmentId;
  const [preview, setPreview] = useState<ReadinessPreview | null>(null);
  const [resolvedId, setResolvedId] = useState<string | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    void loadPendingAssessment().then((pending) => {
      if (cancelled) {
        return;
      }
      if (!pending || !assessmentId || pending.assessment_id !== assessmentId) {
        setPreview(null);
      } else {
        setPreview(pending.preview);
      }
      setResolvedId(assessmentId);
    });
    return () => {
      cancelled = true;
    };
  }, [assessmentId]);

  const status = resolvedId !== assessmentId ? 'loading' : preview ? 'ready' : 'missing';

  function onUnlock() {
    if (!assessmentId || !preview) {
      return;
    }
    if (auth.status !== 'signed_in') {
      router.push({
        pathname: '/sign-in',
        params: { assessmentId, next: 'payment' },
      });
      return;
    }
    router.push(toHref(`/assessment/${assessmentId}/payment`));
  }

  return (
    <PageShell testID="preview-screen">
      {status === 'loading' ? <PreviewSkeleton /> : null}
      {status === 'missing' ? (
        <PageState
          tone="warning"
          happened="This preview is not on this device."
          meaning="Start a new assessment to generate a free preview. Payment is not available from a missing preview."
          consequence="Nothing was charged."
          testID="preview-missing"
          action={<Button label="Start assessment" href={toHref('/assessment/new')} />}
        />
      ) : null}
      {status === 'ready' && preview ? (
        <>
          <PreviewSummary preview={preview} />
          <Button
            label={`Unlock full report — ${REPORT_PRICE_COPY}`}
            testID="unlock-report"
            onPress={onUnlock}
          />
        </>
      ) : null}
    </PageShell>
  );
}
