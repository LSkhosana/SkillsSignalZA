import { StyleSheet, Text, View } from 'react-native';

import { Badge, Divider, WorkspacePanel } from '@/components/system/surfaces';
import { REPORT_PRICE_COPY } from '@/lib/constants';
import type { ReadinessPreview } from '@/services/api';
import { PAID_REPORT_SECTION_KEYS } from '@/services/api';
import { FontFamily, Palette } from '@/theme/tokens';

type PreviewSummaryProps = {
  preview: ReadinessPreview;
};

const LOCKED_LINES = [
  'Category scores and how the points are distributed stay in the full report.',
  'Recorded strengths stay in the full report.',
  'The areas that still need evidence stay in the full report.',
  'The ordered actions stay in the full report.',
  'The recommended project stays in the full report.',
  'Criterion-level evidence notes stay in the full report.',
  'The benchmark statement stays in the full report.',
];

export function PreviewSummary({ preview }: PreviewSummaryProps) {
  const gapLine = preview.priority_gap
    ? `Priority gap: ${preview.priority_gap.criterion_label}`
    : 'No priority gap on this preview.';

  return (
    <View style={styles.stack} testID="preview-summary">
      <Badge label="Free preview" tone="green" />
      <Text style={styles.kicker}>{preview.track_label}</Text>
      <WorkspacePanel>
        <Text style={styles.scoreLabel}>Readiness score</Text>
        <Text style={styles.score} testID="preview-score">
          {preview.final_score} / {preview.score_max}
        </Text>
        <Text style={styles.band} testID="preview-band">
          {preview.band_label}
        </Text>
      </WorkspacePanel>
      <Text style={styles.body}>
        This is the free preview. It shows the score, band and track for this assessment, and nothing beyond that.
      </Text>
      <Text style={styles.body} testID="preview-strongest">
        Strongest area: {preview.strongest_area.label}
      </Text>
      <Text style={styles.body} testID="preview-gap">
        {gapLine}
      </Text>
      <Text style={styles.body}>
        On the {preview.track_label} track, the free preview places this submission in {preview.band_label}. The
        strongest area shown here is {preview.strongest_area.label}.
      </Text>
      <Divider />
      <View testID="preview-paywall" style={styles.lock}>
        <Text style={styles.lockTitle}>What {REPORT_PRICE_COPY} unlocks</Text>
        <Text style={styles.body}>
          One payment of {REPORT_PRICE_COPY} opens the full Readiness Report. Those sections are not part of this free
          preview.
        </Text>
        {LOCKED_LINES.map((line) => (
          <Text key={line} style={styles.lockLine}>
            {line}
          </Text>
        ))}
      </View>
      {PAID_REPORT_SECTION_KEYS.map((key) => (
        <Text key={key} style={styles.hiddenPaidMarker} testID={`preview-absent-${key}`} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  stack: {
    gap: 14,
    minWidth: 0,
  },
  kicker: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  scoreLabel: {
    color: Palette.green,
    fontFamily: FontFamily.sans,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  score: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 64,
    lineHeight: 68,
  },
  band: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 28,
    lineHeight: 32,
  },
  body: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 16,
    lineHeight: 24,
  },
  lock: {
    gap: 8,
    minWidth: 0,
  },
  lockTitle: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 28,
    lineHeight: 32,
  },
  lockLine: {
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 15,
    lineHeight: 22,
  },
  hiddenPaidMarker: {
    height: 0,
  },
});
