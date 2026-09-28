import { Link, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { Button } from '@/components/system/button';
import { StatusPanel } from '@/components/system/feedback';
import { TextField } from '@/components/system/fields';
import { authHref, authResumeHref, firstSearchParam } from '@/lib/auth-resume';
import { resendConfirmationEmail, signUp } from '@/services/auth';
import { FontFamily, Palette } from '@/theme/tokens';

export default function SignUpScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ assessmentId?: string | string[]; next?: string | string[] }>();
  const assessmentId = firstSearchParam(params.assessmentId);
  const next = firstSearchParam(params.next);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [confirmEmail, setConfirmEmail] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resendBusy, setResendBusy] = useState(false);
  const [resent, setResent] = useState(false);

  async function onSubmit() {
    setError(null);
    if (!email.trim() || !email.includes('@')) {
      setError('Enter a valid email address.');
      return;
    }
    if (password.length < 6) {
      setError('Choose a password of at least 6 characters.');
      return;
    }
    setBusy(true);
    try {
      const result = await signUp(email, password);
      if (result.status === 'confirm_email') {
        setConfirmEmail(true);
        return;
      }
      router.replace(authResumeHref(assessmentId, next));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Sign-up is unavailable right now.');
    } finally {
      setBusy(false);
    }
  }

  async function onResend() {
    setError(null);
    setResendBusy(true);
    try {
      await resendConfirmationEmail(email);
      setResent(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The confirmation email could not be sent.');
    } finally {
      setResendBusy(false);
    }
  }

  return (
    <ScreenShell
      title="Create account"
      subtitle="Use an email and password. Confirm the message we send before you continue."
      testID="sign-up-screen"
    >
      {confirmEmail ? (
        <StatusPanel
          tone="success"
          title="Check your email, then sign in"
          message="Your account was created. Open the confirmation message, then sign in to continue this assessment. Nothing was charged."
          testID="confirm-email"
        />
      ) : null}
      {resent ? (
        <StatusPanel
          tone="success"
          title="Confirmation email sent"
          message="If an account exists for this address, another confirmation message is on the way."
        />
      ) : null}
      <TextField
        label="Email"
        value={email}
        onChangeText={setEmail}
        autoComplete="email"
        keyboardType="email-address"
        editable={!confirmEmail}
        testID="sign-up-email"
      />
      <TextField
        label="Password"
        value={password}
        onChangeText={setPassword}
        autoComplete="password"
        secureTextEntry
        editable={!confirmEmail}
        testID="sign-up-password"
      />
      {error ? <StatusPanel tone="danger" title="Could not create account" message={error} testID="auth-error" /> : null}
      {confirmEmail ? (
        <Button
          label="Resend confirmation"
          variant="secondary"
          busy={resendBusy}
          disabled={resendBusy}
          testID="resend-confirmation"
          onPress={() => void onResend()}
        />
      ) : (
        <Button
          label="Create account"
          busy={busy}
          disabled={busy}
          testID="sign-up-submit"
          onPress={() => void onSubmit()}
        />
      )}
      <Link href={authHref('/sign-in', assessmentId, next)} style={styles.link}>
        Already have an account? Sign in
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
