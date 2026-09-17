import { createClient, type SupabaseClient } from '@supabase/supabase-js';

import { getSupabasePublishableKey, getSupabaseUrl } from '@/lib/env';

import { createAuthSessionStorage } from './session-storage';

let client: SupabaseClient | null = null;

export function getSupabaseClient(): SupabaseClient {
  if (client) {
    return client;
  }

  client = createClient(getSupabaseUrl(), getSupabasePublishableKey(), {
    auth: {
      storage: createAuthSessionStorage(),
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: false,
    },
  });

  return client;
}

export function resetSupabaseClientForTests(): void {
  client = null;
}
