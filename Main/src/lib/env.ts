export const PUBLIC_ENV_KEYS = [
  'EXPO_PUBLIC_API_URL',
  'EXPO_PUBLIC_SUPABASE_URL',
  'EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
] as const;

export type PublicEnvKey = (typeof PUBLIC_ENV_KEYS)[number];

function normalize(value: string | undefined): string | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function readEnv(key: PublicEnvKey): string | undefined {
  switch (key) {
    case 'EXPO_PUBLIC_API_URL':
      return normalize(process.env.EXPO_PUBLIC_API_URL);
    case 'EXPO_PUBLIC_SUPABASE_URL':
      return normalize(process.env.EXPO_PUBLIC_SUPABASE_URL);
    case 'EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY':
      return normalize(process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
    default: {
      const exhaustive: never = key;
      return exhaustive;
    }
  }
}

/**
 * Returns a public env value when present. Does not throw.
 */
export function getOptionalPublicEnv(key: PublicEnvKey): string | undefined {
  return readEnv(key);
}

/**
 * Validates a public env variable at the point it is actually used.
 * Missing or empty values fail only for that lookup, so the app can boot
 * without a running server or local `.env` file.
 */
export function requirePublicEnv(key: PublicEnvKey): string {
  const value = readEnv(key);

  if (!value) {
    throw new Error(
      `Missing required environment variable ${key}. Copy Main/.env.example to Main/.env and provide a client-safe value.`,
    );
  }

  return value;
}

export function getApiBaseUrl(): string {
  return requirePublicEnv('EXPO_PUBLIC_API_URL').replace(/\/+$/, '');
}

export function getSupabaseUrl(): string {
  return requirePublicEnv('EXPO_PUBLIC_SUPABASE_URL');
}

export function getSupabasePublishableKey(): string {
  return requirePublicEnv('EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY');
}
