import { useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, Linking, Text } from 'react-native';

import { AccountBar } from '@/components/account-bar';
import { ScreenShell } from '@/components/screen-shell';
import { StatusBanner } from '@/components/status-banner';
import { UiButton } from '@/components/ui-button';
import { useTheme } from '@/hooks/use-theme';
import { toHref } from '@/lib/href';
import { REPORT_POLL_INTERVAL_MS, REPORT_POLL_MAX_ATTEMPTS } from '@/lib/constants';
import { getAccessToken } from '@/services/auth';
import { useAuth } from '@/services/auth/provider';
import { openPaystackCheckout } from '@/services/checkout/paystack';
import {
  checkReportUnlock,
  continueAfterAuthentication,
  startCheckout,
} from '@/services/flow';

type PaymentPhase = 'claiming' | 'checkout' | 'waiting' | 'blocked' | 'error';

export default function PaymentScreen() {
  const theme = useTheme();
  const router = useRouter();
  const auth = useAuth();
  const params = useLocalSearchParams<{ assessmentId?: string | string[] }>();
  const assessmentId = Array.isArray(params.assessmentId) ? params.assessmentId[0] : params.assessmentId;
  const [phase, setPhase] = useState<PaymentPhase>('claiming');
  const [message, setMessage] = useState('Preparing checkout…');
  const [authorizationUrl, setAuthorizationUrl] = useState<string | null>(null);
  const [popupBlocked, setPopupBlocked] = useState(false);
  const pollCount = useRef(0);
  const started = useRef(false);

  const goToAuth = useCallback(() => {
    if (!assessmentId) {
      return;
    }
    router.replace({
      pathname: '/sign-in',
      params: { assessmentId, next: 'payment' },
    });
  }, [assessmentId, router]);

  const inspectReport = useCallback(async () => {
    if (!assessmentId) {
      return;
    }
    const accessToken = await getAccessToken();
    const result = await checkReportUnlock(assessmentId, { accessToken });
    if (result.status === 'unlocked') {
      router.replace(toHref(`/assessment/${assessmentId}/report`));
      return;
    }
    if (result.status === 'needs_auth') {
      goToAuth();
      return;
    }
    if (result.status === 'blocked') {
      setPhase('blocked');
      setMessage(result.message);
      return;
    }
    if (result.status === 'error') {
      setPhase('error');
      setMessage(result.message);
      return;
    }
    setPhase('waiting');
    setMessage('Waiting for payment confirmation. Complete checkout, then check payment.');
  }, [assessmentId, goToAuth, router]);

  const beginCheckout = useCallback(async () => {
    if (!assessmentId) {
      return;
    }
    const accessToken = await getAccessToken();
    if (!accessToken) {
      goToAuth();
      return;
    }

    const claim = await continueAfterAuthentication(assessmentId, { accessToken });
    if (claim.status === 'needs_auth') {
      goToAuth();
      return;
    }
    if (claim.status === 'blocked') {
      setPhase('blocked');
      setMessage(claim.message);
      return;
    }
    if (claim.status === 'error') {
      setPhase('error');
      setMessage(claim.message);
      return;
    }

    const checkout = await startCheckout(assessmentId, { accessToken });
    if (checkout.status === 'needs_auth') {
      goToAuth();
      return;
    }
    if (checkout.status === 'already_unlocked') {
      router.replace(toHref(`/assessment/${assessmentId}/report`));
      return;
    }
    if (checkout.status === 'blocked') {
      setPhase('blocked');
      setMessage(checkout.message);
      return;
    }
    if (checkout.status === 'waiting') {
      setPhase('waiting');
      setMessage(checkout.message);
      return;
    }
    if (checkout.status === 'error') {
      setPhase('error');
      setMessage(checkout.message);
      return;
    }

    setAuthorizationUrl(checkout.authorizationUrl);
    const opened = await openPaystackCheckout(checkout.authorizationUrl);
    setPopupBlocked(opened === 'blocked');
    setPhase('waiting');
    setMessage('Complete checkout in the secure Paystack window. This screen waits for confirmed payment.');
    if (opened === 'returned') {
      await inspectReport();
    }
  }, [assessmentId, goToAuth, inspectReport, router]);

  useEffect(() => {
    if (!assessmentId || auth.status === 'loading' || started.current) {
      return;
    }
    if (auth.status !== 'signed_in') {
      goToAuth();
      return;
    }
    started.current = true;
    const timer = setTimeout(() => {
      void beginCheckout();
    }, 0);
    return () => {
      clearTimeout(timer);
    };
  }, [assessmentId, auth.status, beginCheckout, goToAuth]);

  useEffect(() => {
    if (phase !== 'waiting' || !assessmentId) {
      return;
    }
    pollCount.current = 0;
    const timer = setInterval(() => {
      if (AppState.currentState !== 'active') {
        return;
      }
      pollCount.current += 1;
      if (pollCount.current > REPORT_POLL_MAX_ATTEMPTS) {
        clearInterval(timer);
        return;
      }
      void inspectReport();
    }, REPORT_POLL_INTERVAL_MS);

    return () => {
      clearInterval(timer);
    };
  }, [assessmentId, inspectReport, phase]);

  return (
    <ScreenShell
      title="Unlock full report"
      subtitle="Payment fulfillment is confirmed by the SkillSignalZA report, not by the checkout window closing."
      headerRight={<AccountBar />}
      testID="payment-screen"
    >
      {phase === 'blocked' || phase === 'error' ? (
        <StatusBanner tone="danger" title={phase === 'blocked' ? 'Cannot continue' : 'Payment not ready'} message={message} />
      ) : (
        <StatusBanner
          title={phase === 'waiting' ? 'Waiting for payment' : 'Preparing checkout'}
          message={message}
          testID={phase === 'waiting' ? 'payment-waiting' : 'payment-preparing'}
        />
      )}
      {popupBlocked && authorizationUrl ? (
        <StatusBanner
          title="Secure checkout was blocked"
          message="Use Open secure checkout to continue in a new tab."
        />
      ) : null}
      {authorizationUrl ? (
        <UiButton
          label="Open secure checkout"
          variant="secondary"
          testID="open-checkout"
          onPress={() => {
            void (async () => {
              const opened = await openPaystackCheckout(authorizationUrl);
              setPopupBlocked(opened === 'blocked');
              if (opened === 'blocked') {
                await Linking.openURL(authorizationUrl);
              }
            })();
          }}
        />
      ) : null}
      <UiButton
        label="Check payment"
        testID="check-payment"
        disabled={!assessmentId || phase === 'claiming'}
        onPress={() => void inspectReport()}
      />
      <Text style={{ color: theme.textSecondary, fontSize: 15, lineHeight: 22 }}>
        Checking payment asks Server/ for the report. It does not start another checkout.
      </Text>
    </ScreenShell>
  );
}
