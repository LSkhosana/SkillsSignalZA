import { Link, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { Button } from '@/components/system/button';
import { StatusPanel } from '@/components/system/feedback';
import { TextField } from '@/components/system/fields';
import { authHref, authResumeHref, firstSearchParam } from '@/lib/auth-resume';
import { signIn } from '@/services/auth';
import { FontFamily, Palette } from '@/theme/tokens';

export default function SignInScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{
    assessmentId?: string | string[];
    next?: string | string[];
    reason?: string | string[];
  }>();
  const assessmentId = firstSearchParam(params.assessmentId);
  const next = firstSearchParam(params.next);
  const sessionExpired = firstSearchParam(params.reason) === 'session-expired';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
      router.replace(authResumeHref(assessmentId, next));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Sign-in is unavailable right now.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScreenShell title="Sign in" subtitle="Use your SkillSignalZA email and password." testID="sign-in-screen">
      {sessionExpired ? (
        <StatusPanel
          tone="warning"
          title="Sign in again to continue"
          message="Your session ended. Nothing was charged. Sign in to resume this assessment."
          testID="session-expired-notice"
        />
      ) : null}
      <TextField
        label="Email"
        value={email}
        onChangeText={setEmail}
        autoComplete="email"
        keyboardType="email-address"
        error={error?.startsWith('Enter a valid email') ? error : undefined}
        testID="sign-in-email"
      />
      <TextField
        label="Password"
        value={password}
        onChangeText={setPassword}
        autoComplete="password"
        secureTextEntry
        error={error === 'Enter your password.' ? error : undefined}
        testID="sign-in-password"
      />
      {error && !error.startsWith('Enter a valid email') && error !== 'Enter your password.' ? (
        <StatusPanel tone="danger" title="Could not sign in" message={error} testID="auth-error" />
      ) : null}
      <Button
        label="Sign in"
        busy={busy}
        disabled={busy}
        testID="sign-in-submit"
        onPress={() => void onSubmit()}
      />
      <Link href={authHref('/sign-up', assessmentId, next)} style={styles.link}>
        Create an account
      </Link>
      <Link href={authHref('/forgot-password', assessmentId, next)} style={styles.link}>
        Forgot password
      </Link>
      <Link href="/" style={styles.link}>
        Back to start
      </Link>
      <Text style={styles.body}>
        After you sign in, SkillSignalZA continues the same assessment and checkout. Closing this page does not unlock
        a report.
      </Text>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  body: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 15,
    lineHeight: 22,
  },
  link: {
    color: Palette.green,
    fontFamily: FontFamily.sans,
    fontSize: 16,
    fontWeight: '600',
  },
});
