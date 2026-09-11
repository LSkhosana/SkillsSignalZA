import { StyleSheet, Text, View } from 'react-native';

import { useTheme } from '@/hooks/use-theme';
import { Spacing } from '@/theme';

type StatusBannerProps = {
  tone?: 'info' | 'danger' | 'success';
  title: string;
  message?: string;
  testID?: string;
};

export function StatusBanner({ tone = 'info', title, message, testID }: StatusBannerProps) {
  const theme = useTheme();
  const backgroundColor =
    tone === 'danger' ? theme.dangerSurface : tone === 'success' ? theme.successSurface : theme.background;
  const titleColor = tone === 'danger' ? theme.danger : tone === 'success' ? theme.success : theme.text;

  return (
    <View
      accessibilityRole="alert"
      style={[styles.banner, { backgroundColor, borderColor: theme.border }]}
      testID={testID}
    >
      <Text style={[styles.title, { color: titleColor }]}>{title}</Text>
      {message ? <Text style={[styles.message, { color: theme.textSecondary }]}>{message}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    borderWidth: 1,
    borderRadius: 10,
    padding: Spacing.md,
    gap: Spacing.sm,
  },
  title: {
    fontSize: 16,
    fontWeight: '700',
  },
  message: {
    fontSize: 15,
    lineHeight: 22,
  },
});
