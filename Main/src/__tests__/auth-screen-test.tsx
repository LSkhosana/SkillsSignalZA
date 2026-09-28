import { fireEvent, render, screen } from '@testing-library/react-native';

import { signIn, signUp } from '@/services/auth';

import ForgotPasswordScreen from '../../app/(auth)/forgot-password';
import SessionExpiredScreen from '../../app/(auth)/session-expired';
import SignInScreen from '../../app/(auth)/sign-in';
import SignUpScreen from '../../app/(auth)/sign-up';

const mockReplace = jest.fn();
const mockSearchParams: Record<string, string> = {};

jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  return {
    useRouter: () => ({ push: jest.fn(), replace: mockReplace }),
    useLocalSearchParams: () => mockSearchParams,
    Link: ({ children }: { children: unknown }) => React.createElement(Text, null, children),
  };
});

jest.mock('@/services/auth', () => ({
  signIn: jest.fn(),
  signUp: jest.fn(),
  resendConfirmationEmail: jest.fn(async () => undefined),
  requestPasswordReset: jest.fn(async () => undefined),
  getAccessToken: jest.fn(async () => null),
  updatePassword: jest.fn(),
}));

describe('auth forms', () => {
  beforeEach(() => {
    Object.keys(mockSearchParams).forEach((key) => {
      delete mockSearchParams[key];
    });
    mockReplace.mockClear();
    (signIn as jest.Mock).mockReset();
    (signUp as jest.Mock).mockReset();
  });

  it('validates sign-in fields before calling the auth service', async () => {
    await render(<SignInScreen />);
    await fireEvent.press(screen.getByTestId('sign-in-submit'));
    expect(screen.getByTestId('auth-error')).toHaveTextContent(/Enter a valid email address/);
  });

  it('resumes payment for the original assessment after sign-in', async () => {
    Object.assign(mockSearchParams, { assessmentId: 'a-test-1', next: 'payment' });
    (signIn as jest.Mock).mockResolvedValue({ user: { id: 'u1', email: 'a@b.test' } });
    await render(<SignInScreen />);
    await fireEvent.changeText(screen.getByTestId('sign-in-email'), 'a@b.test');
    await fireEvent.changeText(screen.getByTestId('sign-in-password'), 'password123');
    await fireEvent.press(screen.getByTestId('sign-in-submit'));
    expect(signIn).toHaveBeenCalledWith('a@b.test', 'password123');
    expect(mockReplace).toHaveBeenCalledWith('/assessment/a-test-1/payment');
    expect(JSON.stringify(mockReplace.mock.calls)).not.toMatch(/claim/i);
  });

  it('validates sign-up password length', async () => {
    await render(<SignUpScreen />);
    await fireEvent.changeText(screen.getByTestId('sign-up-email'), 'user@example.com');
    await fireEvent.changeText(screen.getByTestId('sign-up-password'), '123');
    await fireEvent.press(screen.getByTestId('sign-up-submit'));
    expect(screen.getByTestId('auth-error')).toHaveTextContent(/at least 6 characters/);
  });

  it('shows confirmation-required when signup returns no session', async () => {
    (signUp as jest.Mock).mockResolvedValue({ status: 'confirm_email', email: 'user@example.com' });
    await render(<SignUpScreen />);
    await fireEvent.changeText(screen.getByTestId('sign-up-email'), 'user@example.com');
    await fireEvent.changeText(screen.getByTestId('sign-up-password'), 'password123');
    await fireEvent.press(screen.getByTestId('sign-up-submit'));
    expect(await screen.findByTestId('confirm-email')).toHaveTextContent(/Check your email, then sign in/);
    expect(screen.getByTestId('resend-confirmation')).toBeTruthy();
    expect(screen.queryByText(/Supabase/i)).toBeNull();
    expect(screen.queryByText(/Server\//)).toBeNull();
  });

  it('explains a session that ended and keeps assessment context', async () => {
    Object.assign(mockSearchParams, { assessmentId: 'a-test-1', next: 'report' });
    await render(<SessionExpiredScreen />);
    expect(screen.getByTestId('session-expired-state')).toHaveTextContent(/session ended/i);
    expect(screen.getByTestId('session-expired-state')).toHaveTextContent(/Nothing was charged/);
    expect(screen.getByTestId('session-expired-sign-in')).toBeTruthy();
  });

  it('validates forgot-password email before sending a reset message', async () => {
    await render(<ForgotPasswordScreen />);
    await fireEvent.press(screen.getByTestId('forgot-submit'));
    expect(screen.getByTestId('auth-error')).toHaveTextContent(/Enter a valid email address/);
  });
});
