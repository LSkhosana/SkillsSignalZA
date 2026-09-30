import type { ReactNode } from 'react';
import { Platform, StyleSheet, useWindowDimensions, View } from 'react-native';

import { Layout, Palette } from '@/theme/tokens';

export function WorkspaceShell({
  children,
  rail,
  testID,
}: {
  children: ReactNode;
  rail?: ReactNode;
  testID?: string;
}) {
  const { width } = useWindowDimensions();
  const stacked = width < Layout.tablet;

  return (
    <View
      {...(Platform.OS === 'web' ? { className: 'ss-workspace' } : {})}
      style={stacked ? styles.stacked : styles.split}
      testID={testID}
    >
      <View style={styles.workspace}>{children}</View>
      {rail ? (
        <View {...(Platform.OS === 'web' ? { className: 'ss-rail' } : {})} style={stacked ? styles.railStacked : styles.rail}>
          {rail}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  split: {
    width: '100%',
    minWidth: 0,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 28,
  },
  stacked: {
    width: '100%',
    minWidth: 0,
    gap: 20,
  },
  workspace: {
    flex: 1,
    minWidth: 0,
    gap: 16,
  },
  rail: {
    width: Layout.rail,
    maxWidth: '100%',
    gap: 16,
    borderLeftWidth: 1,
    borderLeftColor: Palette.divider,
    paddingLeft: 20,
  },
  railStacked: {
    minWidth: 0,
    gap: 16,
    borderTopWidth: 1,
    borderTopColor: Palette.divider,
    paddingTop: 16,
  },
});
