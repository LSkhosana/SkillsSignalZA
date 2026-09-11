import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';

import { AccountBar } from '@/components/account-bar';
import { ReadinessReportView } from '@/components/readiness-report-view';
import { ScreenShell } from '@/components/screen-shell';
import { StatusBanner } from '@/components/status-banner';
import { UiButton } from '@/components/ui-button';
import { toHref } from '@/lib/href';
import { getAccessToken } from '@/services/auth';
import { useAuth } from '@/services/auth/provider';
import { checkReportUnlock } from '@/services/flow';
import type { ReadinessReport } from '@/services/api';

export default function ReportScreen() {
  const router = useRouter();
  const auth = useAuth();
  const params = useLocalSearchParams<{ assessmentId?: string | string[] }>();
  const assessmentId = Array.isArray(params.assessmentId) ? params.assessmentId[0] : params.assessmentId;
  const [report, setReport] = useState<ReadinessReport | null>(null);
  const [message, setMessage] = useState('Loading report…');
  const [locked, setLocked] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!assessmentId || auth.status === 'loading') {
      return;
    }
    if (auth.status !== 'signed_in') {
      router.replace({
        pathname: '/sign-in',
        params: { assessmentId, next: 'report' },
      });
      return;
    }

    let cancelled = false;
    void (async () => {
      const accessToken = await getAccessToken();
      const result = await checkReportUnlock(assessmentId, { accessToken });
      if (cancelled) {
        return;
      }
      if (result.status === 'unlocked') {
        setReport(result.report);
        setLocked(false);
        setFailed(false);
        return;
      }
      if (result.status === 'needs_auth') {
        router.replace({
          pathname: '/sign-in',
          params: { assessmentId, next: 'report' },
        });
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
    <ScreenShell title="Readiness Report" headerRight={<AccountBar />} testID="report-screen">
      {report ? <ReadinessReportView report={report} /> : null}
      {locked ? (
        <>
          <StatusBanner title="Report locked" message={message} />
          <UiButton
            label="Check payment"
            onPress={() => {
              if (assessmentId) {
                router.replace(toHref(`/assessment/${assessmentId}/payment`));
              }
            }}
          />
        </>
      ) : null}
      {failed ? <StatusBanner tone="danger" title="Report unavailable" message={message} /> : null}
    </ScreenShell>
  );
}
