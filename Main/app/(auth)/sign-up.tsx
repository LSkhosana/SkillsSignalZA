import { Link, useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { useState } from 'react';
import { StyleSheet } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { StatusBanner } from '@/components/status-banner';
import { UiButton } from '@/components/ui-button';
import { UiTextField } from '@/components/ui-text-field';
import { useTheme } from '@/hooks/use-theme';
import { toHref } from '@/lib/href';
import { signUp } from '@/services/auth';

function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default function SignUpScreen() {
  const theme = useTheme();
  const router = useRouter();
  const params = useLocalSearchParams<{ assessmentId?: string | string[]; next?: string | string[] }>();
  const assessmentId = firstParam(params.assessmentId);
  const next = firstParam(params.next);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [confirmEmail, setConfirmEmail] = useState(false);
  const [busy, setBusy] = useState(false);

  function continuePath() {
    if (assessmentId && next === 'report') {
      return toHref(`/assessment/${assessmentId}/report`);
    }
    if (assessmentId) {
      return toHref(`/assessment/${assessmentId}/payment`);
    }
    return toHref('/');
  }

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
      router.replace(continuePath());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Sign-up is unavailable right now.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScreenShell title="Create account" subtitle="Email and password only. Server/ verifies the session token." testID="sign-up-screen">
      {confirmEmail ? (
        <StatusBanner
          tone="success"
          title="Check your email, then sign in"
          message="Your account was created. Confirm the email from Supabase, then sign in to claim this assessment."
          testID="confirm-email"
        />
      ) : null}
      <UiTextField
        label="Email"
        value={email}
        onChangeText={setEmail}
        autoComplete="email"
        keyboardType="email-address"
        testID="sign-up-email"
      />
      <UiTextField
        label="Password"
        value={password}
        onChangeText={setPassword}
        autoComplete="password"
        secureTextEntry
        testID="sign-up-password"
      />
      {error ? <StatusBanner tone="danger" title="Could not create account" message={error} testID="auth-error" /> : null}
      <UiButton
        label={busy ? 'Creating account…' : 'Create account'}
        disabled={busy || confirmEmail}
        testID="sign-up-submit"
        onPress={() => void onSubmit()}
      />
      <Link href={{ pathname: '/sign-in', params: { assessmentId, next } } as unknown as Href} style={[styles.link, { color: theme.accent }]}>
        Already have an account? Sign in
      </Link>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  link: {
    fontSize: 16,
    fontWeight: '600',
  },
});
