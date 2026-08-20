import { Platform } from 'react-native';

import '@/theme/global.css';

export const Colors = {
  light: {
    text: '#111827',
    textSecondary: '#4B5563',
    background: '#F8FAFC',
    surface: '#FFFFFF',
    border: '#E5E7EB',
    accent: '#1D4ED8',
  },
  dark: {
    text: '#F9FAFB',
    textSecondary: '#D1D5DB',
    background: '#0B1220',
    surface: '#111827',
    border: '#374151',
    accent: '#60A5FA',
  },
} as const;

export type ColorSchemeName = keyof typeof Colors;
export type ThemeColor = keyof typeof Colors.light;

export const Spacing = {
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const MaxContentWidth = 720;

export const Fonts = Platform.select({
  web: {
    sans: 'var(--font-display)',
    mono: 'var(--font-mono)',
  },
  default: {
    sans: 'system-ui',
    mono: 'monospace',
  },
});
