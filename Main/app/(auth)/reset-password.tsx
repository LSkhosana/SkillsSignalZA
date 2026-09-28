import { Link, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { Button } from '@/components/system/button';
import { PageState, StatusPanel } from '@/components/system/feedback';
import { TextField } from '@/components/system/fields';
import { authHref, authResumeHref, firstSearchParam } from '@/lib/auth-resume';
import { getAccessToken, updatePassword } from '@/services/auth';
import { FontFamily, Palette } from '@/theme/tokens';

export default function ResetPasswordScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ assessmentId?: string | string[]; next?: string | string[] }>();
  const assessmentId = firstSearchParam(params.assessmentId);
  const next = firstSearchParam(params.next);
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    setError(null);
    if (password.length < 6) {
      setError('Choose a password of at least 6 characters.');
      return;
    }
    setBusy(true);
    try {
      const token = await getAccessToken();
      if (!token) {
        setError('This reset link is invalid or has expired. Request a new email.');
        return;
      }
      await updatePassword(password);
      router.replace(authResumeHref(assessmentId, next));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The password could not be updated.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScreenShell
      title="Reset password"
      subtitle="Choose a new password, then continue the assessment you started."
      testID="reset-password-screen"
    >
      <PageState
        tone="info"
        happened="You opened a password reset link."
        meaning="Set a new password to sign in again. This does not unlock a report by itself."
        consequence="Nothing was charged."
      />
      <TextField
        label="New password"
        value={password}
        onChangeText={setPassword}
        autoComplete="password"
        secureTextEntry
        testID="reset-password"
      />
      {error ? <StatusPanel tone="danger" title="Could not reset password" message={error} testID="auth-error" /> : null}
      <Button
        label="Save new password"
        busy={busy}
        disabled={busy}
        testID="reset-submit"
        onPress={() => void onSubmit()}
      />
      <Link href={authHref('/forgot-password', assessmentId, next)} style={styles.link}>
        Request a new reset email
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
