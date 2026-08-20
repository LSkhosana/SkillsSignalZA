/**
 * Auth integrations will live here. No session provider is wired yet.
 * The API client can attach a bearer token once sign-in exists.
 */
export type AccessToken = string;

export async function getAccessToken(): Promise<AccessToken | null> {
  return null;
}
