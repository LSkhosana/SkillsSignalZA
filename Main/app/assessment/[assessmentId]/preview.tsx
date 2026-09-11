import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';

import { AccountBar } from '@/components/account-bar';
import { PreviewSummary } from '@/components/preview-summary';
import { ScreenShell } from '@/components/screen-shell';
import { StatusBanner } from '@/components/status-banner';
import { UiButton } from '@/components/ui-button';
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
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void loadPendingAssessment().then((pending) => {
      if (cancelled) {
        return;
      }
      if (!pending || !assessmentId || pending.assessment_id !== assessmentId) {
        setMissing(true);
        return;
      }
      setPreview(pending.preview);
    });
    return () => {
      cancelled = true;
    };
  }, [assessmentId]);

  function onUnlock() {
    if (!assessmentId) {
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
    <ScreenShell
      title="Readiness preview"
      subtitle="This is the free preview. Paid report sections stay locked until payment is fulfilled."
      headerRight={<AccountBar />}
      testID="preview-screen"
    >
      {missing || !preview ? (
        <StatusBanner
          tone="danger"
          title="Preview unavailable"
          message="Start a new assessment to generate a preview."
        />
      ) : (
        <PreviewSummary preview={preview} />
      )}
      <UiButton
        label={`Unlock full report — ${REPORT_PRICE_COPY}`}
        disabled={!preview}
        testID="unlock-report"
        onPress={onUnlock}
      />
    </ScreenShell>
  );
}
