import type { ReactNode } from 'react';
import { StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { FontFamily, Layout, Palette } from '@/theme/tokens';

export function SectionHeader({
  eyebrow,
  title,
  subtitle,
  aside,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  aside?: ReactNode;
}) {
  const { width } = useWindowDimensions();
  const compact = width < Layout.mobile;

  return (
    <View style={styles.wrap}>
      <View style={styles.row}>
        <View style={styles.copy}>
          {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
          <Text accessibilityRole="header" style={[styles.title, compact ? styles.titleCompact : null]}>
            {title}
          </Text>
          {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
        </View>
        {aside}
      </View>
      <View style={styles.rule} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: 16,
    minWidth: 0,
  },
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    gap: 16,
  },
  copy: {
    flexGrow: 1,
    flexShrink: 1,
    minWidth: 0,
    gap: 8,
  },
  eyebrow: {
    color: Palette.green,
    fontFamily: FontFamily.sans,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.6,
    textTransform: 'uppercase',
  },
  title: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 44,
    fontWeight: '500',
    letterSpacing: -1,
    lineHeight: 46,
  },
  titleCompact: {
    fontSize: 34,
    lineHeight: 36,
  },
  subtitle: {
    maxWidth: 680,
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 16,
    lineHeight: 24,
  },
  rule: {
    height: 1,
    backgroundColor: Palette.ink,
  },
});
