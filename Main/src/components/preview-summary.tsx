import { StyleSheet, Text, View } from 'react-native';

import { EditionMasthead } from '@/components/edition-masthead';
import { REPORT_PRICE_COPY } from '@/lib/constants';
import type { ReadinessPreview } from '@/services/api';
import { PAID_REPORT_SECTION_KEYS } from '@/services/api';
import { FontFamily, Palette } from '@/theme/tokens';

type PreviewSummaryProps = {
  preview: ReadinessPreview;
};

const LOCKED_SECTIONS = [
  'Category scores',
  'Strengths',
  'Areas to strengthen',
  'Five priority actions',
  'Recommended project',
  'Criterion notes',
  'Benchmark statement',
];

export function PreviewSummary({ preview }: PreviewSummaryProps) {
  const gapLine = preview.priority_gap
    ? preview.priority_gap.criterion_label
    : 'No priority gap on this preview.';

  return (
    <View style={styles.stack} testID="preview-summary">
      <EditionMasthead
        dateline={`Free preview · ${preview.track_label}`}
        score={preview.final_score}
        scoreMax={preview.score_max}
        bandLabel={preview.band_label}
        bandStatement={preview.band_statement}
        disclaimer={preview.disclaimer}
        scoreTestID="preview-score"
        bandTestID="preview-band"
      />
      <View style={styles.leads}>
        <View style={styles.lead} testID="preview-strongest">
          <Text style={styles.kicker}>Strongest area</Text>
          <Text style={styles.leadTitle}>{preview.strongest_area.label}</Text>
        </View>
        <View style={styles.lead} testID="preview-gap">
          <Text style={styles.kicker}>Priority gap</Text>
          <Text style={styles.leadTitle}>{gapLine}</Text>
        </View>
      </View>
      <View testID="preview-paywall" style={styles.lock}>
        <Text style={styles.lockTitle}>What {REPORT_PRICE_COPY} unlocks</Text>
        {LOCKED_SECTIONS.map((line) => (
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
    gap: 22,
    minWidth: 0,
    backgroundColor: Palette.paper,
  },
  leads: {
    gap: 16,
    minWidth: 0,
  },
  lead: {
    gap: 6,
    minWidth: 0,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: Palette.ink,
  },
  kicker: {
    color: Palette.green,
    fontFamily: FontFamily.sans,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  leadTitle: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 24,
    lineHeight: 28,
  },
  lock: {
    gap: 6,
    minWidth: 0,
    paddingTop: 8,
    borderTopWidth: 6,
    borderTopColor: Palette.green,
  },
  lockTitle: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 28,
    lineHeight: 32,
    marginBottom: 4,
  },
  lockLine: {
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 15,
    lineHeight: 22,
  },
  hiddenPaidMarker: {
    height: 0,
    width: 0,
    opacity: 0,
  },
});
