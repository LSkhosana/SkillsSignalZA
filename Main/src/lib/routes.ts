import type { Href } from 'expo-router';

/** Shared customer paths. Legal and My Reports screens are later packages. */
export const Routes = {
  home: '/' as Href,
  assessmentNew: '/assessment/new' as Href,
  signIn: '/sign-in' as Href,
  reports: '/reports' as Href,
  account: '/dashboard' as Href,
  mapPack: '/map-pack' as Href,
  privacy: '/privacy' as Href,
  terms: '/terms' as Href,
  refunds: '/refunds' as Href,
  support: '/support' as Href,
} as const;
