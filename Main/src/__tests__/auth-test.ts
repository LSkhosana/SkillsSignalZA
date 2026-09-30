import {
  getAccessToken,
  getCachedAccessToken,
  requestPasswordReset,
  resendConfirmationEmail,
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
const mockResend = jest.fn();
const mockResetPasswordForEmail = jest.fn();
const mockUpdateUser = jest.fn();
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
      resend: mockResend,
      resetPasswordForEmail: mockResetPasswordForEmail,
      updateUser: mockUpdateUser,
      onAuthStateChange: mockOnAuthStateChange,
    },
  }),
}));

describe('auth service', () => {
  beforeEach(() => {
    resetSupabaseClientForTests();
    setCachedAccessToken(null);
    mockSignUp.mockReset();
    mockSignIn.mockReset();
    mockSignOut.mockReset();
    mockGetSession.mockReset();
    mockResend.mockReset();
    mockResetPasswordForEmail.mockReset();
    mockUpdateUser.mockReset();
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

  it('requests a confirmation resend and a password reset without exposing internals', async () => {
    mockResend.mockResolvedValue({ error: null });
    mockResetPasswordForEmail.mockResolvedValue({ error: null });
    await resendConfirmationEmail('a@b.test');
    await requestPasswordReset('a@b.test', 'https://app.example/reset-password');
    expect(mockResend).toHaveBeenCalledWith({ type: 'signup', email: 'a@b.test' });
    expect(mockResetPasswordForEmail).toHaveBeenCalledWith('a@b.test', {
      redirectTo: 'https://app.example/reset-password',
    });
  });
});
