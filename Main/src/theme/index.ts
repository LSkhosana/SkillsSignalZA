import { Platform } from 'react-native';

import '@/theme/landing.css';
import '@/theme/foundations.css';
import '@/theme/global.css';

import { Palette } from '@/theme/tokens';

export { FontFamily, Layout, Palette } from '@/theme/tokens';

const launchColors = {
  text: Palette.ink,
  textSecondary: Palette.muted,
  background: Palette.paper,
  surface: Palette.surface,
  border: Palette.divider,
  accent: Palette.green,
  danger: Palette.failure,
  dangerSurface: Palette.failureSurface,
  success: Palette.greenDark,
  successSurface: Palette.paleGreen,
  muted: Palette.muted,
  ink: Palette.ink,
  green: Palette.green,
  greenDark: Palette.greenDark,
  greenMid: Palette.greenMid,
  greenSoft: Palette.greenSoft,
  paleGreen: Palette.paleGreen,
  paper: Palette.paper,
  warning: Palette.warning,
  warningSurface: Palette.warningSurface,
} as const;

export const Colors = {
  light: launchColors,
  /** Launch stays on the landing palette. A separate dark theme is not part of this pass. */
  dark: launchColors,
} as const;

export type ColorSchemeName = keyof typeof Colors;
export type ThemeColor = keyof typeof Colors.light;

export const Spacing = {
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const MaxContentWidth = 1320;

export const Fonts = Platform.select({
  web: {
    sans: 'var(--ss-sans)',
    serif: 'var(--ss-serif)',
    mono: 'var(--font-mono)',
  },
  default: {
    sans: 'sans-serif',
    serif: 'serif',
    mono: 'monospace',
  },
});
