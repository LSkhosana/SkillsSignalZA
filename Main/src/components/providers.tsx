import { DefaultTheme, ThemeProvider } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import type { ReactNode } from 'react';

import { AuthProvider } from '@/services/auth/provider';
import { Palette } from '@/theme/tokens';

const launchTheme = {
  ...DefaultTheme,
  dark: false,
  colors: {
    ...DefaultTheme.colors,
    primary: Palette.green,
    background: Palette.paper,
    card: Palette.surface,
    text: Palette.ink,
    border: Palette.divider,
    notification: Palette.green,
  },
};

type ProvidersProps = {
  children: ReactNode;
};

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider value={launchTheme}>
      <AuthProvider>
        {children}
        <StatusBar style="dark" />
      </AuthProvider>
    </ThemeProvider>
  );
}
