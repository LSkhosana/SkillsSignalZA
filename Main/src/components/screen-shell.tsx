import type { ReactNode } from 'react';
import { ScrollView, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useTheme } from '@/hooks/use-theme';
import { MaxContentWidth, Spacing } from '@/theme';

type ScreenShellProps = {
  title: string;
  subtitle?: string;
  headerRight?: ReactNode;
  children: ReactNode;
  testID?: string;
};

export function ScreenShell({ title, subtitle, headerRight, children, testID }: ScreenShellProps) {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const horizontalPadding = width >= 768 ? Spacing.xl : Spacing.md;

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: theme.background }]} testID={testID}>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={[
          styles.scrollContent,
          { paddingHorizontal: horizontalPadding, maxWidth: MaxContentWidth },
        ]}
      >
        <View style={[styles.card, { backgroundColor: theme.surface, borderColor: theme.border }]}>
          <View style={styles.titleRow}>
            <Text style={[styles.title, { color: theme.text, flex: 1 }]}>{title}</Text>
            {headerRight}
          </View>
          {subtitle ? <Text style={[styles.subtitle, { color: theme.textSecondary }]}>{subtitle}</Text> : null}
          {children}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    width: '100%',
    alignSelf: 'center',
    paddingVertical: Spacing.lg,
  },
  card: {
    borderWidth: 1,
    borderRadius: 12,
    padding: Spacing.lg,
    gap: Spacing.md,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
  },
  subtitle: {
    fontSize: 16,
    lineHeight: 24,
  },
});
