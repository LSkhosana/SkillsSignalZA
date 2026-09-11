import {
  getAccessToken,
  getCachedAccessToken,
  setCachedAccessToken,
  signIn,
  signOut,
  signUp,
} from '@/services/auth';
import { resetSupabaseClientForTests } from '@/services/auth/client';

const mockSignUp = jest.fn();
const mockSignIn = jest.fn();
const mockSignOut = jest.fn();
const mockGetSession = jest.fn();
const mockOnAuthStateChange = jest.fn(() => ({
  data: { subscription: { unsubscribe: jest.fn() } },
}));

jest.mock('@supabase/supabase-js', () => ({
  createClient: () => ({
    auth: {
      signUp: mockSignUp,
      signInWithPassword: mockSignIn,
      signOut: mockSignOut,
      getSession: mockGetSession,
      onAuthStateChange: mockOnAuthStateChange,
    },
  }),
}));

describe('Supabase auth service', () => {
  beforeEach(() => {
    resetSupabaseClientForTests();
    setCachedAccessToken(null);
    mockSignUp.mockReset();
    mockSignIn.mockReset();
    mockSignOut.mockReset();
    mockGetSession.mockReset();
  });

  it('signs in and caches the access token', async () => {
    mockSignIn.mockResolvedValue({
      data: {
        session: { access_token: 'access-token', user: { id: 'user-1', email: 'a@b.test' } },
        user: { id: 'user-1', email: 'a@b.test' },
      },
      error: null,
    });
    const result = await signIn('a@b.test', 'password123');
    expect(result.user.email).toBe('a@b.test');
    expect(getCachedAccessToken()).toBe('access-token');
    expect(mockSignIn).toHaveBeenCalledWith({ email: 'a@b.test', password: 'password123' });
  });

  it('returns confirm-email when signup has no session', async () => {
    mockSignUp.mockResolvedValue({
      data: { session: null, user: { id: 'user-1', email: 'a@b.test' } },
      error: null,
    });
    const result = await signUp('a@b.test', 'password123');
    expect(result).toEqual({ status: 'confirm_email', email: 'a@b.test' });
    expect(getCachedAccessToken()).toBeNull();
  });

  it('clears authenticated session state on sign-out', async () => {
    setCachedAccessToken('access-token');
    mockGetSession.mockResolvedValue({ data: { session: null }, error: null });
    mockSignOut.mockResolvedValue({ error: null });
    await signOut();
    expect(getCachedAccessToken()).toBeNull();
    expect(await getAccessToken()).toBeNull();
    expect(mockSignOut).toHaveBeenCalled();
  });
});
