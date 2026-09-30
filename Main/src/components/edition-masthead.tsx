import { Platform, StyleSheet, Text, View } from 'react-native';

import { FontFamily, Palette } from '@/theme/tokens';

type EditionMastheadProps = {
  dateline: string;
  score: number;
  scoreMax: number;
  bandLabel: string;
  bandStatement: string;
  scopeStatement?: string;
  disclaimer?: string;
  testID?: string;
  scoreTestID?: string;
  bandTestID?: string;
  disclaimerTestID?: string;
};

function webClass(className: string) {
  return Platform.OS === 'web' ? { className } : {};
}

export function EditionMasthead({
  dateline,
  score,
  scoreMax,
  bandLabel,
  bandStatement,
  scopeStatement,
  disclaimer,
  testID,
  scoreTestID,
  bandTestID,
  disclaimerTestID,
}: EditionMastheadProps) {
  return (
    <View {...webClass('ss-edition-masthead')} style={styles.masthead} testID={testID}>
      <Text {...webClass('ss-edition-dateline')} style={styles.dateline}>
        {dateline}
      </Text>
      <View {...webClass('ss-edition-rule')} style={styles.rule} />
      <Text {...webClass('ss-edition-score')} style={styles.score} testID={scoreTestID}>
        {score}
        <Text style={styles.scoreMax}> / {scoreMax}</Text>
      </Text>
      <Text {...webClass('ss-edition-deck')} style={styles.deck} testID={bandTestID}>
        {bandLabel}
      </Text>
      {bandStatement ? <Text style={styles.statement}>{bandStatement}</Text> : null}
      {scopeStatement || disclaimer ? (
        <View testID={disclaimerTestID} style={styles.benchmark}>
          {scopeStatement ? <Text style={styles.disclaimer}>{scopeStatement}</Text> : null}
          {disclaimer ? <Text style={styles.disclaimer}>{disclaimer}</Text> : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  masthead: {
    gap: 12,
    minWidth: 0,
    backgroundColor: Palette.paper,
  },
  dateline: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  rule: {
    height: 6,
    backgroundColor: Palette.green,
    width: '100%',
  },
  score: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 84,
    lineHeight: 88,
    letterSpacing: -2,
    flexShrink: 1,
  },
  scoreMax: {
    color: Palette.muted,
    fontFamily: FontFamily.serif,
    fontSize: 28,
    lineHeight: 36,
  },
  deck: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 28,
    lineHeight: 34,
    flexShrink: 1,
  },
  statement: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 20,
    lineHeight: 28,
    maxWidth: 720,
  },
  benchmark: {
    gap: 6,
    maxWidth: 720,
  },
  disclaimer: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 13,
    lineHeight: 20,
  },
});
