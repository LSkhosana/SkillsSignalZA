import { Link } from 'expo-router';
import type { Href } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/services/auth/provider';

export function AccountBar() {
  const theme = useTheme();
  const auth = useAuth();

  if (auth.status === 'loading') {
    return <Text style={[styles.meta, { color: theme.textSecondary }]}>Checking session…</Text>;
  }

  if (auth.status !== 'signed_in') {
    return (
      <View style={styles.row}>
        <Link href="/sign-in" style={[styles.link, { color: theme.accent }]}>
          Sign in
        </Link>
        <Link href={'/sign-up' as unknown as Href} style={[styles.link, { color: theme.accent }]}>
          Sign up
        </Link>
      </View>
    );
  }

  return (
    <View style={styles.row}>
      <Text style={[styles.meta, { color: theme.textSecondary }]}>{auth.user?.email ?? 'Signed in'}</Text>
      <Pressable accessibilityRole="button" accessibilityLabel="Sign out" onPress={() => void auth.signOut()}>
        <Text style={[styles.link, { color: theme.accent }]}>Sign out</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    alignItems: 'center',
  },
  link: {
    fontSize: 16,
    fontWeight: '600',
  },
  meta: {
    fontSize: 14,
  },
});
