import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import { PreviewSummary } from '@/components/preview-summary';
import { ScreenShell } from '@/components/screen-shell';
import { Button } from '@/components/system/button';
import { PageState } from '@/components/system/feedback';
import { PreviewSkeleton } from '@/components/system/skeleton';
import { WorkspacePanel } from '@/components/system/surfaces';
import { WorkspaceShell } from '@/components/system/workspace-shell';
import { REPORT_PRICE_COPY } from '@/lib/constants';
import { toHref } from '@/lib/href';
import type { ReadinessPreview } from '@/services/api';
import { useAuth } from '@/services/auth/provider';
import { loadPendingAssessment } from '@/services/flow';
import { FontFamily, Palette } from '@/theme/tokens';

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
    <ScreenShell
      title="Free preview"
      subtitle="This is the free preview. The full report stays locked until payment is fulfilled."
      testID="preview-screen"
    >
      <WorkspaceShell
        rail={
          <WorkspacePanel>
            <Text style={styles.eyebrow}>Full report</Text>
            <Text style={styles.price}>{REPORT_PRICE_COPY}</Text>
            <Text style={styles.note}>
              One payment unlocks the full Readiness Report. Paid sections are not shown here.
            </Text>
          </WorkspacePanel>
        }
      >
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
      </WorkspaceShell>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  eyebrow: {
    color: Palette.green,
    fontFamily: FontFamily.sans,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  price: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 32,
    lineHeight: 36,
  },
  note: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 15,
    lineHeight: 22,
  },
});
