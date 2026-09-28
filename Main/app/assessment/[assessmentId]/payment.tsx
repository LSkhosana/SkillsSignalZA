import { useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, Linking, StyleSheet, Text } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { Button } from '@/components/system/button';
import { PageState, StatusPanel } from '@/components/system/feedback';
import { WorkspacePanel } from '@/components/system/surfaces';
import { WorkspaceShell } from '@/components/system/workspace-shell';
import { authHref, firstSearchParam } from '@/lib/auth-resume';
import {
  REPORT_POLL_INTERVAL_MS,
  REPORT_POLL_MAX_ATTEMPTS,
  REPORT_PRICE_COPY,
  REPORT_PRODUCT_NAME,
  REPORT_UNLOCK_LINES,
} from '@/lib/constants';
import { toHref } from '@/lib/href';
import {
  canCheckPayment,
  canReopenCheckout,
  canStartPaymentInitialization,
  shouldMarkPaymentDelayed,
  type PaymentPhase,
} from '@/lib/payment-workspace';
import { getAccessToken } from '@/services/auth';
import { useAuth } from '@/services/auth/provider';
import { openPaystackCheckout } from '@/services/checkout/paystack';
import {
  checkReportUnlock,
  continueAfterAuthentication,
  loadPendingAssessment,
  startCheckout,
} from '@/services/flow';
import { FontFamily, Palette } from '@/theme/tokens';

export default function PaymentScreen() {
  const router = useRouter();
  const auth = useAuth();
  const params = useLocalSearchParams<{ assessmentId?: string | string[] }>();
  const assessmentId = firstSearchParam(params.assessmentId);
  const [phase, setPhase] = useState<PaymentPhase>('claiming');
  const [message, setMessage] = useState('Connecting this assessment to your account.');
  const [authorizationUrl, setAuthorizationUrl] = useState<string | null>(null);
  const [popupBlocked, setPopupBlocked] = useState(false);
  const [trackLabel, setTrackLabel] = useState('Selected track');
  const [initializing, setInitializing] = useState(false);
  const pollCount = useRef(0);
  const claimed = useRef(false);
  const startLock = useRef(false);
  const phaseRef = useRef<PaymentPhase>('claiming');

  const goToAuth = useCallback(
    (expired: boolean) => {
      if (!assessmentId) {
        return;
      }
      router.replace(authHref(expired ? '/session-expired' : '/sign-in', assessmentId, 'payment'));
    },
    [assessmentId, router],
  );

  const inspectReport = useCallback(async () => {
    if (!assessmentId) {
      return;
    }
    const accessToken = await getAccessToken();
    const result = await checkReportUnlock(assessmentId, { accessToken });
    if (result.status === 'unlocked') {
      setPhase('succeeded');
      router.replace(toHref(`/assessment/${assessmentId}/report`));
      return;
    }
    if (result.status === 'needs_auth') {
      goToAuth(auth.status === 'signed_in');
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
    if (phaseRef.current === 'summary' || phaseRef.current === 'error') {
      return;
    }
    pollCount.current += 1;
    if (shouldMarkPaymentDelayed(pollCount.current, REPORT_POLL_MAX_ATTEMPTS, true)) {
      setPhase('delayed');
      setMessage('Payment confirmation is taking longer than usual. Do not pay again.');
      return;
    }
    setPhase((current) => (current === 'delayed' ? 'delayed' : 'waiting'));
    setMessage('Waiting for payment confirmation. Complete checkout, then check payment. Do not pay twice.');
  }, [assessmentId, auth.status, goToAuth, router]);

  const attachAssessment = useCallback(async () => {
    if (!assessmentId) {
      return;
    }
    const accessToken = await getAccessToken();
    if (!accessToken) {
      goToAuth(false);
      return;
    }

    const claim = await continueAfterAuthentication(assessmentId, { accessToken });
    if (claim.status === 'needs_auth') {
      goToAuth(true);
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

    const pending = await loadPendingAssessment();
    if (pending?.preview.track_label) {
      setTrackLabel(pending.preview.track_label);
    }
    setPhase('summary');
    setMessage('Review this order, then continue to secure payment.');
  }, [assessmentId, goToAuth]);

  const beginCheckout = useCallback(async () => {
    if (!assessmentId || startLock.current || authorizationUrl) {
      return;
    }
    if (phase !== 'summary' && phase !== 'error') {
      return;
    }
    startLock.current = true;
    setInitializing(true);
    setPhase('initializing');
    setMessage('Opening secure checkout. This does not unlock the report by itself.');
    try {
      const accessToken = await getAccessToken();
      if (!accessToken) {
        startLock.current = false;
        goToAuth(false);
        return;
      }

      const checkout = await startCheckout(assessmentId, { accessToken });
      if (checkout.status === 'needs_auth') {
        startLock.current = false;
        goToAuth(true);
        return;
      }
      if (checkout.status === 'already_unlocked') {
        setPhase('succeeded');
        router.replace(toHref(`/assessment/${assessmentId}/report`));
        return;
      }
      if (checkout.status === 'blocked') {
        startLock.current = false;
        setPhase('blocked');
        setMessage(checkout.message);
        return;
      }
      if (checkout.status === 'waiting') {
        setPhase('waiting');
        setMessage(`${checkout.message} Do not pay again.`);
        return;
      }
      if (checkout.status === 'error') {
        startLock.current = false;
        setPhase('error');
        setMessage(checkout.message);
        return;
      }

      setAuthorizationUrl(checkout.authorizationUrl);
      const opened = await openPaystackCheckout(checkout.authorizationUrl);
      setPopupBlocked(opened === 'blocked');
      setPhase('checkout_opened');
      setMessage('Complete checkout in the secure window. Closing it does not unlock the report.');
      if (opened === 'returned') {
        await inspectReport();
      } else {
        setPhase('waiting');
        setMessage('Waiting for payment confirmation. Check payment on this screen. Do not pay twice.');
      }
    } finally {
      setInitializing(false);
    }
  }, [assessmentId, authorizationUrl, goToAuth, inspectReport, phase, router]);

  const reopenCheckout = useCallback(async () => {
    if (!authorizationUrl || !canReopenCheckout(phase, authorizationUrl)) {
      return;
    }
    const opened = await openPaystackCheckout(authorizationUrl);
    setPopupBlocked(opened === 'blocked');
    if (opened === 'blocked') {
      await Linking.openURL(authorizationUrl);
    }
    setPhase('checkout_opened');
    setMessage('Complete checkout in the secure window. Closing it does not unlock the report.');
  }, [authorizationUrl, phase]);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  useEffect(() => {
    if (!assessmentId || auth.status === 'loading' || claimed.current) {
      return;
    }
    if (auth.status !== 'signed_in') {
      goToAuth(false);
      return;
    }
    claimed.current = true;
    const timer = setTimeout(() => {
      void attachAssessment();
    }, 0);
    return () => {
      clearTimeout(timer);
    };
  }, [assessmentId, attachAssessment, auth.status, goToAuth]);

  useEffect(() => {
    if ((phase !== 'waiting' && phase !== 'checkout_opened') || !assessmentId) {
      return;
    }
    const timer = setInterval(() => {
      if (AppState.currentState !== 'active') {
        return;
      }
      void inspectReport();
    }, REPORT_POLL_INTERVAL_MS);

    return () => {
      clearInterval(timer);
    };
  }, [assessmentId, inspectReport, phase]);

  const continueDisabled = !canStartPaymentInitialization(phase, initializing, Boolean(authorizationUrl));

  return (
    <ScreenShell
      title="Unlock full report"
      subtitle="Pay once. SkillSignalZA unlocks the report only after payment is confirmed."
      testID="payment-screen"
    >
      <WorkspaceShell
        rail={
          <WorkspacePanel>
            <Text style={styles.eyebrow}>{REPORT_PRODUCT_NAME}</Text>
            <Text style={styles.price}>{REPORT_PRICE_COPY}</Text>
            <Text style={styles.note}>One-time payment. Closing checkout does not unlock the report.</Text>
          </WorkspacePanel>
        }
      >
        {phase === 'claiming' ? (
          <StatusPanel title="Preparing checkout" message={message} testID="payment-preparing" />
        ) : null}

        {phase === 'summary' || phase === 'error' ? (
          <WorkspacePanel testID="order-summary">
            <Text style={styles.eyebrow}>Order summary</Text>
            <Text style={styles.summaryTitle}>{REPORT_PRODUCT_NAME}</Text>
            <Text style={styles.body}>Track: {trackLabel}</Text>
            <Text style={styles.body}>Amount: {REPORT_PRICE_COPY}</Text>
            <Text style={styles.body}>This is a one-time payment. It is not a subscription.</Text>
            <Text style={styles.body}>The full report unlocks:</Text>
            {REPORT_UNLOCK_LINES.map((line) => (
              <Text key={line} style={styles.body}>
                {line}
              </Text>
            ))}
          </WorkspacePanel>
        ) : null}

        {phase === 'initializing' ? (
          <StatusPanel title="Opening secure payment" message={message} testID="payment-initializing" />
        ) : null}
        {phase === 'checkout_opened' ? (
          <StatusPanel title="Checkout opened" message={message} testID="payment-opened" />
        ) : null}
        {phase === 'waiting' ? (
          <StatusPanel title="Waiting for payment" message={message} testID="payment-waiting" />
        ) : null}
        {phase === 'delayed' ? (
          <PageState
            tone="warning"
            happened={message}
            meaning="Checkout may already be complete. Closing the payment window does not unlock the report."
            consequence="Do not pay again. Check payment on this screen until SkillSignalZA confirms the report is unlocked."
            testID="payment-delayed"
          />
        ) : null}
        {phase === 'blocked' ? (
          <PageState
            tone="danger"
            happened={message}
            meaning="This assessment cannot continue to payment on this account."
            consequence="Nothing extra was started from this screen. Start a new assessment or sign in with the account that owns this one."
            testID="payment-blocked"
          />
        ) : null}
        {phase === 'error' && message ? (
          <PageState
            tone="danger"
            happened={message}
            meaning="Secure checkout did not start. The report is still locked."
            consequence="Nothing was charged by this attempt. You can try Continue to secure payment again."
            testID="payment-error"
          />
        ) : null}

        {popupBlocked && authorizationUrl ? (
          <StatusPanel
            title="Secure checkout was blocked"
            message="Use Open secure checkout to continue in a new tab."
          />
        ) : null}

        {phase === 'summary' || phase === 'error' ? (
          <Button
            label="Continue to secure payment"
            disabled={continueDisabled}
            busy={initializing}
            testID="continue-payment"
            onPress={() => void beginCheckout()}
          />
        ) : null}
        {authorizationUrl ? (
          <Button
            label="Open secure checkout"
            variant="secondary"
            disabled={!canReopenCheckout(phase, authorizationUrl)}
            testID="open-checkout"
            onPress={() => void reopenCheckout()}
          />
        ) : null}
        <Button
          label="Check payment"
          variant="secondary"
          testID="check-payment"
          disabled={!assessmentId || !canCheckPayment(phase)}
          onPress={() => void inspectReport()}
        />
        <Text style={styles.note}>
          Checking payment asks SkillSignalZA whether this report is unlocked. It does not start another checkout.
        </Text>
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
  summaryTitle: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 28,
    lineHeight: 32,
  },
  body: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 16,
    lineHeight: 24,
  },
});
