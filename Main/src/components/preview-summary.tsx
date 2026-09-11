import { StyleSheet, Text, View } from 'react-native';

import { useTheme } from '@/hooks/use-theme';
import { REPORT_PRICE_COPY } from '@/lib/constants';
import type { ReadinessPreview } from '@/services/api';
import { PAID_REPORT_SECTION_KEYS } from '@/services/api';
import { Spacing } from '@/theme';

type PreviewSummaryProps = {
  preview: ReadinessPreview;
};

export function PreviewSummary({ preview }: PreviewSummaryProps) {
  const theme = useTheme();

  return (
    <View style={styles.stack} testID="preview-summary">
      <Text style={[styles.kicker, { color: theme.textSecondary }]}>{preview.track_label}</Text>
      <Text style={[styles.score, { color: theme.text }]} testID="preview-score">
        {preview.final_score} / {preview.score_max}
      </Text>
      <Text style={[styles.band, { color: theme.text }]} testID="preview-band">
        {preview.band_label}
      </Text>
      <Text style={[styles.meta, { color: theme.textSecondary }]} testID="preview-strongest">
        Strongest area: {preview.strongest_area.label}
      </Text>
      <Text style={[styles.meta, { color: theme.textSecondary }]} testID="preview-gap">
        {preview.priority_gap
          ? `Priority gap: ${preview.priority_gap.criterion_label}`
          : 'No priority gap on this preview.'}
      </Text>
      <View style={[styles.lock, { borderColor: theme.border }]} testID="preview-paywall">
        <Text style={[styles.lockTitle, { color: theme.text }]}>Full Readiness Report is locked</Text>
        <Text style={[styles.lockBody, { color: theme.textSecondary }]}>
          Category breakdown, strengths, material gaps, priority actions, project recommendation, and
          criterion breakdown unlock after a one-time {REPORT_PRICE_COPY} payment.
        </Text>
      </View>
      {PAID_REPORT_SECTION_KEYS.map((key) => (
        <Text key={key} style={styles.hiddenPaidMarker} testID={`preview-absent-${key}`} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  stack: {
    gap: Spacing.sm,
  },
  kicker: {
    fontSize: 14,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  score: {
    fontSize: 32,
    fontWeight: '700',
  },
  band: {
    fontSize: 20,
    fontWeight: '600',
  },
  meta: {
    fontSize: 16,
    lineHeight: 24,
  },
  lock: {
    borderWidth: 1,
    borderRadius: 10,
    padding: Spacing.md,
    gap: Spacing.sm,
    marginTop: Spacing.sm,
  },
  lockTitle: {
    fontSize: 16,
    fontWeight: '700',
  },
  lockBody: {
    fontSize: 15,
    lineHeight: 22,
  },
  hiddenPaidMarker: {
    height: 0,
  },
});
