import { Platform, StyleSheet, View } from 'react-native';

import { Palette } from '@/theme/tokens';

export function SkeletonBlock({ width = '100%' as const, height = 14 }: { width?: number | `${number}%`; height?: number }) {
  if (Platform.OS === 'web') {
    return (
      <div className="ss-skeleton" aria-hidden="true">
        <span style={{ width: typeof width === 'number' ? `${width}px` : width, height }} />
      </div>
    );
  }

  return <View style={[styles.block, { width, height }]} />;
}

function SkeletonCopy({ lines = 3 }: { lines?: number }) {
  return (
    <View accessibilityElementsHidden style={styles.stack}>
      {Array.from({ length: lines }, (_, index) => (
        <SkeletonBlock key={index} height={11} width={index === lines - 1 ? '72%' : '100%'} />
      ))}
    </View>
  );
}

export function AppBootSkeleton() {
  return (
    <View accessibilityLabel="Loading SkillSignalZA" accessibilityState={{ busy: true }} style={styles.frame}>
      <SkeletonBlock height={18} width={160} />
      <SkeletonBlock height={42} width="86%" />
      <SkeletonCopy />
    </View>
  );
}

export function PreviewSkeleton() {
  return (
    <View accessibilityLabel="Loading preview" accessibilityState={{ busy: true }} style={styles.frame}>
      <SkeletonBlock height={12} width={120} />
      <SkeletonBlock height={64} width={140} />
      <SkeletonBlock height={28} width="70%" />
      <SkeletonCopy lines={2} />
      <SkeletonBlock height={44} width={220} />
    </View>
  );
}

export function ReportSkeleton() {
  return (
    <View accessibilityLabel="Loading report" accessibilityState={{ busy: true }} style={styles.frame}>
      <View style={styles.reportRow}>
        <View style={styles.scoreWell}>
          <SkeletonBlock height={12} width={80} />
          <SkeletonBlock height={72} width={100} />
        </View>
        <View style={styles.reportMain}>
          <SkeletonBlock height={36} width="80%" />
          <SkeletonCopy lines={4} />
        </View>
      </View>
    </View>
  );
}

export function MyReportsSkeleton() {
  return (
    <View accessibilityLabel="Loading reports" accessibilityState={{ busy: true }} style={styles.frame}>
      <SkeletonBlock height={32} width="56%" />
      {[0, 1, 2].map((item) => (
        <View key={item} style={styles.reportLine}>
          <SkeletonBlock height={18} width="46%" />
          <SkeletonBlock height={12} width="28%" />
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  block: {
    backgroundColor: '#E8EBE8',
  },
  stack: {
    gap: 9,
  },
  frame: {
    gap: 16,
    minWidth: 0,
  },
  reportRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 16,
  },
  scoreWell: {
    width: 180,
    minHeight: 160,
    gap: 12,
    padding: 16,
    backgroundColor: Palette.ink,
  },
  reportMain: {
    flex: 1,
    minWidth: 220,
    gap: 12,
  },
  reportLine: {
    gap: 8,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: Palette.divider,
  },
});
