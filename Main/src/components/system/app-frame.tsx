import type { ReactNode } from 'react';
import { Platform, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { usePathname } from 'expo-router';

import { AppHeader } from '@/components/system/app-header';
import { ToastProvider } from '@/components/system/feedback';
import { useEditorialReveal } from '@/hooks/use-editorial-reveal';
import '@/theme/app-styles';
import { Palette } from '@/theme/tokens';

export function AppFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  useEditorialReveal();
  const marketingSite = Platform.OS === 'web' && pathname === '/';

  if (marketingSite) {
    return <ToastProvider>{children}</ToastProvider>;
  }

  return (
    <ToastProvider>
      <SafeAreaView edges={['top', 'left', 'right']} style={styles.frame} testID="app-frame">
        <View style={styles.rule} {...(Platform.OS === 'web' ? { className: 'ss-no-print' } : {})} />
        <AppHeader />
        <View style={styles.body}>{children}</View>
      </SafeAreaView>
    </ToastProvider>
  );
}

const styles = StyleSheet.create({
  frame: {
    flex: 1,
    overflow: 'hidden',
    backgroundColor: Palette.paper,
  },
  rule: {
    height: 5,
    backgroundColor: Palette.green,
  },
  body: {
    flex: 1,
    minWidth: 0,
    minHeight: 0,
  },
});
