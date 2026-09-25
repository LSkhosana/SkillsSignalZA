import { useState, type ReactNode } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { FontFamily, Layout, Palette } from '@/theme/tokens';

function webClass(className: string) {
  return Platform.OS === 'web' ? { className } : {};
}

export function EditorialCard({ children, testID }: { children: ReactNode; testID?: string }) {
  return (
    <View {...webClass('ss-panel')} style={styles.card} testID={testID}>
      {children}
    </View>
  );
}

export function WorkspacePanel({ children, testID }: { children: ReactNode; testID?: string }) {
  return (
    <View {...webClass('ss-panel')} style={styles.card} testID={testID}>
      {children}
    </View>
  );
}

export function Divider() {
  return <View accessibilityElementsHidden importantForAccessibility="no" style={styles.divider} />;
}

type BadgeTone = 'neutral' | 'green' | 'warning' | 'danger';

const badgeClass: Record<BadgeTone, string> = {
  neutral: 'ss-badge',
  green: 'ss-badge ss-badge-green',
  warning: 'ss-badge ss-badge-warning',
  danger: 'ss-badge ss-badge-danger',
};

export function Badge({ label, tone = 'neutral', testID }: { label: string; tone?: BadgeTone; testID?: string }) {
  const palette = {
    neutral: { color: Palette.ink, backgroundColor: Palette.paperDeep, borderColor: Palette.divider },
    green: { color: Palette.greenDark, backgroundColor: Palette.paleGreen, borderColor: '#B7D4C3' },
    warning: { color: Palette.warning, backgroundColor: Palette.warningSurface, borderColor: '#D8BC72' },
    danger: { color: Palette.failure, backgroundColor: Palette.failureSurface, borderColor: '#E7B4B4' },
  }[tone];

  return (
    <Text {...webClass(badgeClass[tone])} style={[styles.badge, palette]} testID={testID}>
      {label}
    </Text>
  );
}

export function StateLabel({ label, detail, tone = 'neutral' }: { label: string; detail?: string; tone?: BadgeTone }) {
  return (
    <View style={styles.stateRow}>
      <Badge label={label} tone={tone} />
      {detail ? <Text style={styles.stateDetail}>{detail}</Text> : null}
    </View>
  );
}

export function ProgressBar({ label, value, testID }: { label: string; value: number; testID?: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  const rounded = Math.round(clamped);

  return (
    <View style={styles.progress} testID={testID}>
      <View style={styles.progressMeta}>
        <Text style={styles.progressLabel}>{label}</Text>
        <Text style={styles.progressValue}>{rounded}</Text>
      </View>
      <View
        accessibilityRole="progressbar"
        accessibilityLabel={label}
        accessibilityValue={{ min: 0, max: 100, now: rounded }}
        {...webClass('ss-meter-track')}
        style={styles.track}
      >
        <View {...webClass('ss-meter-fill')} style={[styles.fill, { width: `${clamped}%` }]} />
      </View>
    </View>
  );
}

export function Accordion({
  title,
  children,
  defaultExpanded = false,
  testID,
}: {
  title: string;
  children: ReactNode;
  defaultExpanded?: boolean;
  testID?: string;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <View style={styles.accordion}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={title}
        accessibilityState={{ expanded }}
        onPress={() => setExpanded((current) => !current)}
        style={styles.accordionHeader}
        testID={testID}
      >
        <Text style={styles.accordionTitle}>{title}</Text>
        <Text style={styles.accordionMark}>{expanded ? '−' : '+'}</Text>
      </Pressable>
      {expanded ? (
        <View {...webClass('ss-accordion-panel')} style={styles.accordionPanel}>
          {children}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    minWidth: 0,
    backgroundColor: Palette.surface,
    borderWidth: 1,
    borderColor: Palette.divider,
    borderRadius: 0,
    padding: 22,
    gap: 12,
  },
  divider: {
    height: 1,
    backgroundColor: Palette.divider,
  },
  badge: {
    alignSelf: 'flex-start',
    overflow: 'hidden',
    borderWidth: 1,
    borderRadius: 0,
    paddingHorizontal: 7,
    paddingVertical: 4,
    fontFamily: FontFamily.sans,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.1,
    textTransform: 'uppercase',
  },
  stateRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 8,
  },
  stateDetail: {
    flexShrink: 1,
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 13,
    lineHeight: 18,
  },
  progress: {
    gap: 8,
    minWidth: 0,
  },
  progressMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  progressLabel: {
    flexShrink: 1,
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 13,
    fontWeight: '700',
  },
  progressValue: {
    color: Palette.muted,
    fontFamily: FontFamily.serif,
    fontSize: 16,
  },
  track: {
    height: 7,
    backgroundColor: '#E7E9E6',
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
    backgroundColor: Palette.green,
  },
  accordion: {
    borderTopWidth: 1,
    borderTopColor: Palette.ink,
  },
  accordionHeader: {
    minHeight: Layout.touch,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    paddingVertical: 10,
  },
  accordionTitle: {
    flex: 1,
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 22,
  },
  accordionMark: {
    color: Palette.green,
    fontFamily: FontFamily.sans,
    fontSize: 20,
    fontWeight: '700',
  },
  accordionPanel: {
    paddingBottom: 14,
  },
});
