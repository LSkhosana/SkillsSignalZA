import { Platform } from 'react-native';

/**
 * Mirrors the custom properties in landing.css.
 * That file is the visual source of truth for the launch system.
 */
export const Palette = {
  ink: '#101413',
  inkSoft: '#262B28',
  green: '#217346',
  greenDark: '#185C37',
  greenMid: '#3C9D68',
  greenSoft: '#80C19C',
  paleGreen: '#E9F4EE',
  paper: '#F7F6F0',
  paperDeep: '#ECEBE4',
  surface: '#FFFFFF',
  divider: '#D7D9D3',
  muted: '#666D69',
  warning: '#8A5A08',
  warningSurface: '#FFF6DF',
  failure: '#7C2929',
  failureRule: '#A92D2D',
  failureSurface: '#FFF1F1',
  onGreen: '#FFFFFF',
  footerMuted: '#A9B3AD',
} as const;

export const Layout = {
  canvas: 1320,
  rail: 300,
  tablet: 980,
  mobile: 680,
  touch: 44,
  header: 78,
} as const;

export const FontFamily = {
  serif: Platform.select({
    web: 'Iowan Old Style, Palatino Linotype, Palatino, Baskerville, Georgia, Times New Roman, serif',
    ios: 'Georgia',
    default: 'serif',
  }),
  sans: Platform.select({
    web: 'Inter, Segoe UI, Arial, sans-serif',
    ios: 'System',
    android: 'sans-serif',
    default: 'sans-serif',
  }),
} as const;
