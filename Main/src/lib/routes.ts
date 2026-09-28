import type { Href } from 'expo-router';

/** Shared customer paths. Legal screens are a later package. */
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
