import type { Session } from '@supabase/supabase-js';
import { createContext, createElement, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import {
  restoreSession,
  setCachedAccessToken,
  signOut as signOutSession,
  subscribeToAuthChanges,
  type AuthUser,
} from '@/services/auth';

export type AuthStatus = 'loading' | 'signed_out' | 'signed_in';

export type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  accessToken: string | null;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function userFromSession(session: Session | null): AuthUser | null {
  if (!session?.user) {
    return null;
  }
  return {
    id: session.user.id,
    email: session.user.email ?? null,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    let cancelled = false;

    void restoreSession().then((restored) => {
      if (cancelled) {
        return;
      }
      setSession(restored);
      setStatus(restored ? 'signed_in' : 'signed_out');
    });

    const unsubscribe = subscribeToAuthChanges((next) => {
      if (cancelled) {
        return;
      }
      setSession(next);
      setStatus(next ? 'signed_in' : 'signed_out');
    });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: userFromSession(session),
      accessToken: session?.access_token ?? null,
      signOut: async () => {
        await signOutSession();
        setCachedAccessToken(null);
        setSession(null);
        setStatus('signed_out');
      },
    }),
    [session, status],
  );

  return createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error('useAuth must be used within AuthProvider.');
  }
  return value;
}
