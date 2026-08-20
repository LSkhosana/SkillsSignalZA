import { Link } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { useTheme } from '@/hooks/use-theme';
import { getHealth } from '@/services/api';

export default function DashboardScreen() {
  const theme = useTheme();
  const [healthMessage, setHealthMessage] = useState('Checking API health…');

  useEffect(() => {
    let cancelled = false;

    void getHealth().then((result) => {
      if (cancelled) {
        return;
      }

      if (result.ok) {
        setHealthMessage(`API health: ${result.data.status}`);
        return;
      }

      setHealthMessage(`API unavailable: ${result.error.message}`);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ScreenShell title="Dashboard">
      <Text style={[styles.body, { color: theme.textSecondary }]}>
        Signed-in product screens will live in this route group. Scoring stays in Server/.
      </Text>
      <Text style={[styles.body, { color: theme.textSecondary }]}>{healthMessage}</Text>
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
