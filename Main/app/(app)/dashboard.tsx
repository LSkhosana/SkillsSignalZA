import { Link } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/services/auth/provider';

export default function DashboardScreen() {
  const theme = useTheme();
  const auth = useAuth();

  return (
    <ScreenShell title="Account">
      <Text style={[styles.body, { color: theme.textSecondary }]}>
        Assessment history is not part of this release. Continue from a new assessment or an existing preview.
      </Text>
      <Text style={[styles.body, { color: theme.textSecondary }]}>
        {auth.status === 'signed_in' ? `Signed in as ${auth.user?.email ?? 'your account'}.` : 'You are signed out.'}
      </Text>
      <Link href="/" style={[styles.link, { color: theme.accent }]}>
        Back to start
      </Link>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  body: {
    fontSize: 16,
    lineHeight: 24,
  },
  link: {
    fontSize: 16,
    fontWeight: '600',
  },
});
