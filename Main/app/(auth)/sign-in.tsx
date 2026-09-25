import { Link, useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { StatusBanner } from '@/components/status-banner';
import { UiButton } from '@/components/ui-button';
import { UiTextField } from '@/components/ui-text-field';
import { useTheme } from '@/hooks/use-theme';
import { signIn } from '@/services/auth';
import { toHref } from '@/lib/href';

function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default function SignInScreen() {
  const theme = useTheme();
  const router = useRouter();
  const params = useLocalSearchParams<{ assessmentId?: string | string[]; next?: string | string[] }>();
  const assessmentId = firstParam(params.assessmentId);
  const next = firstParam(params.next);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
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
    if (!password) {
      setError('Enter your password.');
      return;
    }
    setBusy(true);
    try {
      await signIn(email, password);
      router.replace(continuePath());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Sign-in is unavailable right now.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScreenShell title="Sign in" subtitle="Use your SkillSignalZA email and password." testID="sign-in-screen">
      <UiTextField
        label="Email"
        value={email}
        onChangeText={setEmail}
        autoComplete="email"
        keyboardType="email-address"
        testID="sign-in-email"
      />
      <UiTextField
        label="Password"
        value={password}
        onChangeText={setPassword}
        autoComplete="password"
        secureTextEntry
        testID="sign-in-password"
      />
      {error ? <StatusBanner tone="danger" title="Could not sign in" message={error} testID="auth-error" /> : null}
      <UiButton label={busy ? 'Signing in…' : 'Sign in'} disabled={busy} testID="sign-in-submit" onPress={() => void onSubmit()} />
      <Link href={{ pathname: '/sign-up', params: { assessmentId, next } } as unknown as Href} style={[styles.link, { color: theme.accent }]}>
        Create an account
      </Link>
      <Link href="/" style={[styles.link, { color: theme.accent }]}>
        Back to start
      </Link>
      <Text style={[styles.body, { color: theme.textSecondary }]}>
        After you sign in, SkillSignalZA claims the same assessment and continues checkout. Tokens are never placed in
        the URL.
      </Text>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  body: {
    fontSize: 15,
    lineHeight: 22,
  },
  link: {
    fontSize: 16,
    fontWeight: '600',
  },
});
