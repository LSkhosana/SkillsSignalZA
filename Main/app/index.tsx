import { Link } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { useTheme } from '@/hooks/use-theme';

export default function WelcomeScreen() {
  const theme = useTheme();

  return (
    <ScreenShell title="SkillSignalZA">
      <Text style={[styles.body, { color: theme.textSecondary }]}>
        Universal customer app scaffold for web, Android, and iOS. This welcome screen exists to
        confirm routing and responsive layout.
      </Text>
      <Link href="/sign-in" style={[styles.link, { color: theme.accent }]}>
        Sign in
      </Link>
      <Link href="/dashboard" style={[styles.link, { color: theme.accent }]}>
        Dashboard
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
