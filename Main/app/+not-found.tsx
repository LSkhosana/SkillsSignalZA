import { Link, Stack } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { useTheme } from '@/hooks/use-theme';

export default function NotFoundScreen() {
  const theme = useTheme();

  return (
    <>
      <Stack.Screen options={{ title: 'Not found' }} />
      <ScreenShell title="Screen not found">
        <Text style={[styles.body, { color: theme.textSecondary }]}>
          That route is not part of this scaffold.
        </Text>
        <Link href="/" style={[styles.link, { color: theme.accent }]}>
          Go to welcome
        </Link>
      </ScreenShell>
    </>
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
