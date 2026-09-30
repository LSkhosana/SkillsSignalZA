import type { Session, User } from '@supabase/supabase-js';

import { getOptionalPublicEnv } from '@/lib/env';

import { getSupabaseClient } from './client';

export type AccessToken = string;

export type AuthUser = {
  id: string;
  email: string | null;
};

export type SignInResult = {
  session: Session;
  user: AuthUser;
};

export type SignUpResult =
  | { status: 'signed_in'; session: Session; user: AuthUser }
  | { status: 'confirm_email'; email: string };

export function hasSupabaseConfig(): boolean {
  return Boolean(
    getOptionalPublicEnv('EXPO_PUBLIC_SUPABASE_URL') &&
      getOptionalPublicEnv('EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY'),
  );
}

let cachedAccessToken: string | null = null;

export function getCachedAccessToken(): string | null {
  return cachedAccessToken;
}

export function setCachedAccessToken(token: string | null): void {
  cachedAccessToken = token;
}

function toAuthUser(user: User): AuthUser {
  return {
    id: user.id,
    email: user.email ?? null,
  };
}

function customerAuthError(message: string): Error {
  return new Error(message);
}

function mapAuthError(message: string, fallback: string): Error {
  const lowered = message.toLowerCase();
  if (lowered.includes('invalid login') || lowered.includes('invalid credentials')) {
    return customerAuthError('Email or password is incorrect.');
  }
  if (lowered.includes('already registered') || lowered.includes('already been registered')) {
    return customerAuthError('An account with this email already exists. Sign in instead.');
  }
  if (lowered.includes('not confirmed') || lowered.includes('email not confirmed')) {
    return customerAuthError('Confirm your email, then sign in.');
  }
  if (lowered.includes('expired') || lowered.includes('invalid token') || lowered.includes('otp')) {
    return customerAuthError('This link has expired. Request a new email and try again.');
  }
  if (lowered.includes('password')) {
    return customerAuthError('Choose a stronger password of at least 6 characters.');
  }
  if (lowered.includes('email')) {
    return customerAuthError('Enter a valid email address.');
  }
  return customerAuthError(fallback);
}

function mapSupabaseAuthError(message: string): Error {
  return mapAuthError(message, 'Sign-in is unavailable right now. Try again shortly.');
}

export async function getAccessToken(): Promise<AccessToken | null> {
  if (!hasSupabaseConfig()) {
    return cachedAccessToken;
  }
  try {
    const { data, error } = await getSupabaseClient().auth.getSession();
    if (error) {
      cachedAccessToken = null;
      return null;
    }
    cachedAccessToken = data.session?.access_token ?? null;
    return cachedAccessToken;
  } catch {
    cachedAccessToken = null;
    return null;
  }
}

export async function restoreSession(): Promise<Session | null> {
  if (!hasSupabaseConfig()) {
    cachedAccessToken = null;
    return null;
  }
  try {
    const { data, error } = await getSupabaseClient().auth.getSession();
    if (error) {
      cachedAccessToken = null;
      return null;
    }
    cachedAccessToken = data.session?.access_token ?? null;
    return data.session ?? null;
  } catch {
    cachedAccessToken = null;
    return null;
  }
}

export function subscribeToAuthChanges(
  listener: (session: Session | null) => void,
): () => void {
  if (!hasSupabaseConfig()) {
    return () => undefined;
  }
  const { data } = getSupabaseClient().auth.onAuthStateChange((_event, session) => {
    cachedAccessToken = session?.access_token ?? null;
    listener(session);
  });

  return () => {
    data.subscription.unsubscribe();
  };
}

export async function signUp(email: string, password: string): Promise<SignUpResult> {
  if (!hasSupabaseConfig()) {
    throw customerAuthError('Sign-in is unavailable right now. Try again shortly.');
  }
  const { data, error } = await getSupabaseClient().auth.signUp({
    email: email.trim(),
    password,
  });

  if (error) {
    throw mapSupabaseAuthError(error.message);
  }

  if (!data.session) {
    return { status: 'confirm_email', email: email.trim() };
  }

  cachedAccessToken = data.session.access_token;
  return {
    status: 'signed_in',
    session: data.session,
    user: toAuthUser(data.user ?? data.session.user),
  };
}

export async function signIn(email: string, password: string): Promise<SignInResult> {
  if (!hasSupabaseConfig()) {
    throw customerAuthError('Sign-in is unavailable right now. Try again shortly.');
  }
  const { data, error } = await getSupabaseClient().auth.signInWithPassword({
    email: email.trim(),
    password,
  });

  if (error || !data.session || !data.user) {
    throw mapSupabaseAuthError(error?.message ?? 'Email or password is incorrect.');
  }

  cachedAccessToken = data.session.access_token;
  return {
    session: data.session,
    user: toAuthUser(data.user),
  };
}

export async function signOut(): Promise<void> {
  cachedAccessToken = null;
  if (!hasSupabaseConfig()) {
    return;
  }
  try {
    await getSupabaseClient().auth.signOut();
  } finally {
    cachedAccessToken = null;
  }
}

export async function resendConfirmationEmail(email: string): Promise<void> {
  if (!hasSupabaseConfig()) {
    throw customerAuthError('Email confirmation is unavailable right now. Try again shortly.');
  }
  const { error } = await getSupabaseClient().auth.resend({
    type: 'signup',
    email: email.trim(),
  });
  if (error) {
    throw mapAuthError(error.message, 'The confirmation email could not be sent. Try again shortly.');
  }
}

export async function requestPasswordReset(email: string, redirectTo: string): Promise<void> {
  if (!hasSupabaseConfig()) {
    throw customerAuthError('Password reset is unavailable right now. Try again shortly.');
  }
  const { error } = await getSupabaseClient().auth.resetPasswordForEmail(email.trim(), { redirectTo });
  if (error) {
    throw mapAuthError(error.message, 'The reset email could not be sent. Try again shortly.');
  }
}

export async function updatePassword(password: string): Promise<void> {
  if (!hasSupabaseConfig()) {
    throw customerAuthError('Password reset is unavailable right now. Try again shortly.');
  }
  const { error } = await getSupabaseClient().auth.updateUser({ password });
  if (error) {
    throw mapAuthError(error.message, 'The password could not be updated. Request a new reset email.');
  }
}

export { getSupabaseClient, resetSupabaseClientForTests } from './client';
