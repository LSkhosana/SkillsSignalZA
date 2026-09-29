import { StyleSheet, Text, View } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { StatusPanel } from '@/components/system/feedback';
import type { LegalDocumentCopy } from '@/lib/legal-copy';
import { FontFamily, Palette } from '@/theme/tokens';

export function LegalDocument({ copy, testID }: { copy: LegalDocumentCopy; testID: string }) {
  return (
    <ScreenShell title={copy.title} subtitle={copy.subtitle} testID={testID}>
      {copy.unpublished ? (
        <StatusPanel tone="warning" title="Not yet published" message={copy.unpublished} testID={`${testID}-unpublished`} />
      ) : null}
      <View style={styles.stack}>
        {copy.sections.map((section) => (
          <View key={section.heading} style={styles.section}>
            <Text accessibilityRole="header" style={styles.heading}>
              {section.heading}
            </Text>
            {section.paragraphs.map((paragraph) => (
              <Text key={paragraph} style={styles.body}>
                {paragraph}
              </Text>
            ))}
          </View>
        ))}
      </View>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  stack: {
    gap: 28,
    minWidth: 0,
  },
  section: {
    gap: 10,
    minWidth: 0,
  },
  heading: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 28,
    lineHeight: 32,
  },
  body: {
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 16,
    lineHeight: 24,
    maxWidth: '100%',
  },
});
