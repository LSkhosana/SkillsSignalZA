import * as Linking from 'expo-linking';
import { Link, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { StyleSheet } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { Button } from '@/components/system/button';
import { StatusPanel } from '@/components/system/feedback';
import { TextField } from '@/components/system/fields';
import { authHref, firstSearchParam } from '@/lib/auth-resume';
import { requestPasswordReset } from '@/services/auth';
import { FontFamily, Palette } from '@/theme/tokens';

function resetRedirectUrl(): string {
  if (typeof window !== 'undefined' && window.location?.origin) {
    return `${window.location.origin}/reset-password`;
  }
  return Linking.createURL('/reset-password');
}

export default function ForgotPasswordScreen() {
  const params = useLocalSearchParams<{ assessmentId?: string | string[]; next?: string | string[] }>();
  const assessmentId = firstSearchParam(params.assessmentId);
  const next = firstSearchParam(params.next);
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    setError(null);
    if (!email.trim() || !email.includes('@')) {
      setError('Enter a valid email address.');
      return;
    }
    setBusy(true);
    try {
      await requestPasswordReset(email, resetRedirectUrl());
      setSent(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The reset email could not be sent.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScreenShell
      title="Forgot password"
      subtitle="We will send a reset link to your email. Nothing about your assessments is changed by this request."
      testID="forgot-password-screen"
    >
      {sent ? (
        <StatusPanel
          tone="success"
          title="Check your email"
          message="If an account exists for this address, a reset message is on the way. Use the link to choose a new password."
          testID="reset-email-sent"
        />
      ) : null}
      <TextField
        label="Email"
        value={email}
        onChangeText={setEmail}
        autoComplete="email"
        keyboardType="email-address"
        error={error?.startsWith('Enter a valid email') ? error : undefined}
        testID="forgot-email"
      />
      {error && !error.startsWith('Enter a valid email') ? (
        <StatusPanel tone="danger" title="Could not send reset email" message={error} testID="auth-error" />
      ) : null}
      <Button
        label="Send reset email"
        busy={busy}
        disabled={busy || sent}
        testID="forgot-submit"
        onPress={() => void onSubmit()}
      />
      <Link href={authHref('/sign-in', assessmentId, next)} style={styles.link}>
        Back to sign in
      </Link>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  link: {
    color: Palette.green,
    fontFamily: FontFamily.sans,
    fontSize: 16,
    fontWeight: '600',
  },
});
