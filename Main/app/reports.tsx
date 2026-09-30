import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { Button } from '@/components/system/button';
import { EmptyState, PageState } from '@/components/system/feedback';
import { MyReportsSkeleton } from '@/components/system/skeleton';
import { Badge, EditorialCard, StateLabel } from '@/components/system/surfaces';
import { authHref } from '@/lib/auth-resume';
import {
  bandLabelForId,
  formatCustomerDate,
  summaryScoreLine,
  trackLabelForId,
} from '@/lib/assessment-summaries';
import { toHref } from '@/lib/href';
import { Routes } from '@/lib/routes';
import { customerMessageFromError, isAuthError, listOwnedAssessments, type AssessmentSummaryItem } from '@/services/api';
import { getAccessToken } from '@/services/auth';
import { useAuth } from '@/services/auth/provider';
import { FontFamily, Palette } from '@/theme/tokens';

export default function ReportsScreen() {
  const router = useRouter();
  const auth = useAuth();
  const [items, setItems] = useState<AssessmentSummaryItem[] | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    if (auth.status === 'loading') {
      return;
    }
    if (auth.status !== 'signed_in') {
      router.replace(authHref('/sign-in', undefined, 'reports'));
      return;
    }

    let cancelled = false;
    void (async () => {
      const accessToken = await getAccessToken();
      const result = await listOwnedAssessments({ accessToken });
      if (cancelled) {
        return;
      }
      setLoading(false);
      if (!result.ok) {
        if (isAuthError(result.error)) {
          router.replace(authHref('/session-expired', undefined, 'reports'));
          return;
        }
        setFailed(
          customerMessageFromError(result.error, 'Your reports could not be loaded. Try again shortly.'),
        );
        setItems(null);
        return;
      }
      setFailed(null);
      setItems(result.data.items);
    })();

    return () => {
      cancelled = true;
    };
  }, [auth.status, reload, router]);

  return (
    <ScreenShell
      title="My Reports"
      subtitle="Reports you own stay on this account. Sign in later to reopen a purchased report."
      testID="reports-screen"
    >
      {loading && items == null && failed == null ? <MyReportsSkeleton /> : null}
      {failed ? (
        <PageState
          tone="danger"
          happened={failed}
          meaning="My Reports could not be loaded from SkillSignalZA."
          consequence="Nothing was charged or lost by opening this page. Sign in again if the session ended, or retry shortly."
          testID="reports-unavailable"
          action={
            <Button
              label="Try again"
              variant="secondary"
              testID="reports-retry"
              onPress={() => {
                setFailed(null);
                setLoading(true);
                setReload((value) => value + 1);
              }}
            />
          }
        />
      ) : null}
      {items && items.length === 0 ? (
        <EmptyState
          title="No reports yet"
          message="Start an assessment to get a free preview. After you unlock a Readiness Report, it will appear here."
          testID="reports-empty"
          action={<Button label="Start assessment" href={Routes.assessmentNew} testID="reports-start-assessment" />}
        />
      ) : null}
      {items && items.length > 0 ? (
        <View style={styles.list} testID="reports-list">
          {items.map((item) => (
            <ReportEntry key={item.assessment_id} item={item} />
          ))}
        </View>
      ) : null}
    </ScreenShell>
  );
}

function ReportEntry({ item }: { item: AssessmentSummaryItem }) {
  const router = useRouter();
  const unlocked = item.access_state === 'UNLOCKED';
  const band = bandLabelForId(item.band);

  return (
    <EditorialCard testID={`report-entry-${item.assessment_id}`}>
      <StateLabel
        label={unlocked ? 'Unlocked' : 'Preview'}
        tone={unlocked ? 'green' : 'warning'}
        detail={unlocked ? 'Purchased Readiness Report' : 'Not purchased'}
      />
      <Text style={styles.track}>{trackLabelForId(item.track)}</Text>
      <Text style={styles.score}>{summaryScoreLine(item)}</Text>
      {band ? <Text style={styles.band}>{band}</Text> : <Text style={styles.quiet}>Band not available yet</Text>}
      <Text style={styles.quiet}>Assessed {formatCustomerDate(item.assessed_at)}</Text>
      {item.unlocked_at ? (
        <Text style={styles.quiet}>Unlocked {formatCustomerDate(item.unlocked_at)}</Text>
      ) : null}
      {unlocked ? (
        <Button
          label="View report"
          testID={`view-report-${item.assessment_id}`}
          onPress={() => router.push(toHref(`/assessment/${item.assessment_id}/report`))}
        />
      ) : (
        <View style={styles.previewActions}>
          <Badge label="Locked report" tone="warning" />
          <Button
            label="Continue to unlock"
            variant="secondary"
            testID={`continue-unlock-${item.assessment_id}`}
            onPress={() => router.push(toHref(`/assessment/${item.assessment_id}/payment`))}
          />
        </View>
      )}
    </EditorialCard>
  );
}

const styles = StyleSheet.create({
  list: {
    gap: 16,
    minWidth: 0,
  },
  track: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  score: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 36,
    lineHeight: 40,
    maxWidth: '100%',
    flexShrink: 1,
  },
  band: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 22,
    lineHeight: 26,
    maxWidth: '100%',
    flexShrink: 1,
  },
  quiet: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 14,
    lineHeight: 20,
    maxWidth: '100%',
    flexShrink: 1,
  },
  previewActions: {
    gap: 12,
    alignItems: 'flex-start',
  },
});
