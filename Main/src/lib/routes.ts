import type { Href } from 'expo-router';

export const LEGAL_PATHS = ['/privacy', '/terms', '/refunds', '/support'] as const;

export const MARKETING_FOOTER_LINKS = [
  { label: 'About the benchmark', href: '#benchmark' },
  { label: 'Career Map Pack', href: '#career-map-pack' },
  { label: 'Privacy', href: '/privacy' },
  { label: 'Terms', href: '/terms' },
  { label: 'Refunds', href: '/refunds' },
  { label: 'Support', href: '/support' },
] as const;

export const Routes = {
  home: '/' as Href,
  assessmentNew: '/assessment/new' as Href,
  signIn: '/sign-in' as Href,
  signUp: '/sign-up' as Href,
  forgotPassword: '/forgot-password' as Href,
  resetPassword: '/reset-password' as Href,
  sessionExpired: '/session-expired' as Href,
  reports: '/reports' as Href,
  account: '/dashboard' as Href,
  mapPack: '/map-pack' as Href,
  privacy: '/privacy' as Href,
  terms: '/terms' as Href,
  refunds: '/refunds' as Href,
  support: '/support' as Href,
} as const;
