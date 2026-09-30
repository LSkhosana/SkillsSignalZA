import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';

import { ReadinessReportView } from '@/components/readiness-report-view';
import { Button } from '@/components/system/button';
import { PageShell } from '@/components/system/page-shell';
import { PageState } from '@/components/system/feedback';
import { ReportSkeleton } from '@/components/system/skeleton';
import { authHref, firstSearchParam } from '@/lib/auth-resume';
import { toHref } from '@/lib/href';
import { getAccessToken } from '@/services/auth';
import { useAuth } from '@/services/auth/provider';
import { checkReportUnlock } from '@/services/flow';
import type { ReadinessReport } from '@/services/api';

export default function ReportScreen() {
  const router = useRouter();
  const auth = useAuth();
  const params = useLocalSearchParams<{ assessmentId?: string | string[] }>();
  const assessmentId = firstSearchParam(params.assessmentId);
  const [report, setReport] = useState<ReadinessReport | null>(null);
  const [message, setMessage] = useState('Loading report…');
  const [locked, setLocked] = useState(false);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!assessmentId || auth.status === 'loading') {
      return;
    }
    if (auth.status !== 'signed_in') {
      router.replace(authHref('/sign-in', assessmentId, 'report'));
      return;
    }

    let cancelled = false;
    void (async () => {
      const accessToken = await getAccessToken();
      const result = await checkReportUnlock(assessmentId, { accessToken });
      if (cancelled) {
        return;
      }
      setLoading(false);
      if (result.status === 'unlocked') {
        setReport(result.report);
        setLocked(false);
        setFailed(false);
        return;
      }
      if (result.status === 'needs_auth') {
        router.replace(authHref('/session-expired', assessmentId, 'report'));
        return;
      }
      if (result.status === 'locked') {
        setLocked(true);
        setMessage('The report is still locked. Complete payment, then try again.');
        return;
      }
      setFailed(true);
      setMessage(result.message);
    })();

    return () => {
      cancelled = true;
    };
  }, [assessmentId, auth.status, router]);

  return (
    <PageShell testID="report-screen">
      {loading && !report && !locked && !failed ? <ReportSkeleton /> : null}
      {report ? <ReadinessReportView report={report} /> : null}
      {locked ? (
        <PageState
          tone="warning"
          happened={message}
          meaning="Closing checkout or returning from payment does not unlock this report. SkillSignalZA unlocks it only after payment is confirmed."
          consequence="Nothing extra was charged by opening this page. Continue to payment and check payment there."
          testID="report-locked"
          action={
            <Button
              label="Check payment"
              onPress={() => {
                if (assessmentId) {
                  router.replace(toHref(`/assessment/${assessmentId}/payment`));
                }
              }}
            />
          }
        />
      ) : null}
      {failed ? (
        <PageState
          tone="danger"
          happened={message}
          meaning="This report cannot be opened on this account right now."
          consequence="Nothing was changed by this attempt. Sign in with the owning account or start a new assessment."
          testID="report-unavailable"
        />
      ) : null}
    </PageShell>
  );
}
