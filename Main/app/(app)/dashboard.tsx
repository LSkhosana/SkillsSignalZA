import { Link } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { Button } from '@/components/system/button';
import { maskAccountLabel } from '@/components/system/account-menu';
import { Routes } from '@/lib/routes';
import { useAuth } from '@/services/auth/provider';
import { FontFamily, Palette } from '@/theme/tokens';

export default function DashboardScreen() {
  const auth = useAuth();

  return (
    <ScreenShell
      title="Account"
      subtitle="Reports you own stay with this account. They are not stored in the original browser session."
    >
      <Text style={styles.body}>
        {auth.status === 'signed_in'
          ? `Signed in as ${maskAccountLabel(auth.user?.email)}.`
          : 'You are signed out.'}
      </Text>
      <Button label="My Reports" href={Routes.reports} testID="account-my-reports" />
      <Button label="Start new assessment" href={Routes.assessmentNew} variant="secondary" />
      <Link href="/" style={styles.link}>
        Back to start
      </Link>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  body: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 16,
    lineHeight: 24,
  },
  link: {
    color: Palette.green,
    fontFamily: FontFamily.sans,
    fontSize: 16,
    fontWeight: '600',
  },
});
