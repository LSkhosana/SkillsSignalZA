import { useLocalSearchParams } from 'expo-router';

import { ScreenShell } from '@/components/screen-shell';
import { Button } from '@/components/system/button';
import { PageState } from '@/components/system/feedback';
import { authHref, firstSearchParam } from '@/lib/auth-resume';

export default function SessionExpiredScreen() {
  const params = useLocalSearchParams<{ assessmentId?: string | string[]; next?: string | string[] }>();
  const assessmentId = firstSearchParam(params.assessmentId);
  const next = firstSearchParam(params.next);

  return (
    <ScreenShell
      title="Session ended"
      subtitle="Sign in again to continue. Your assessment is still on this device."
      testID="session-expired-screen"
    >
      <PageState
        tone="warning"
        happened="Your sign-in session ended."
        meaning="You need to sign in again to claim this assessment, continue checkout, or open a paid report."
        consequence="Nothing was charged and no assessment was lost."
        testID="session-expired-state"
        action={
          <Button
            label="Sign in"
            href={authHref('/sign-in', assessmentId, next)}
            testID="session-expired-sign-in"
          />
        }
      />
    </ScreenShell>
  );
}
