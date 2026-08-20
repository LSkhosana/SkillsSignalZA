import { Link } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { useTheme } from '@/hooks/use-theme';

export default function SignInScreen() {
  const theme = useTheme();

  return (
    <ScreenShell title="Sign in">
      <Text style={[styles.body, { color: theme.textSecondary }]}>
        Authentication is not wired yet. This screen only proves the auth route group.
      </Text>
      <Link href="/" style={[styles.link, { color: theme.accent }]}>
        Back to welcome
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
