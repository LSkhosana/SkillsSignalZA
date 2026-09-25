import type { ReactNode } from 'react';
import { ScrollView, StyleSheet, useWindowDimensions, View } from 'react-native';

import { GlobalFooter } from '@/components/system/global-footer';
import { Layout, Palette } from '@/theme/tokens';

export function PageShell({
  children,
  testID,
  footer = true,
}: {
  children: ReactNode;
  testID?: string;
  footer?: boolean;
}) {
  const { width } = useWindowDimensions();
  const padding = width < Layout.mobile ? 16 : 24;

  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      style={styles.scroll}
      contentContainerStyle={styles.content}
      testID={testID}
    >
      <View style={[styles.main, { paddingHorizontal: padding }]}>{children}</View>
      {footer ? <GlobalFooter /> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: {
    flex: 1,
    backgroundColor: Palette.paper,
  },
  content: {
    flexGrow: 1,
    width: '100%',
  },
  main: {
    flexGrow: 1,
    width: '100%',
    maxWidth: Layout.canvas,
    alignSelf: 'center',
    minWidth: 0,
    gap: 16,
    paddingTop: 28,
    paddingBottom: 40,
  },
});
