import { fireEvent, render, screen } from '@testing-library/react-native';

import { signUp } from '@/services/auth';

import SignInScreen from '../../app/(auth)/sign-in';
import SignUpScreen from '../../app/(auth)/sign-up';

jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  return {
    useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
    useLocalSearchParams: () => ({}),
    Link: ({ children }: { children: unknown }) => React.createElement(Text, null, children),
  };
});

jest.mock('@/services/auth', () => ({
  signIn: jest.fn(),
  signUp: jest.fn(),
}));

describe('auth forms', () => {
  it('validates sign-in fields before calling Supabase', async () => {
    await render(<SignInScreen />);
    await fireEvent.press(screen.getByTestId('sign-in-submit'));
    expect(screen.getByTestId('auth-error')).toHaveTextContent(/Enter a valid email address/);
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
  });
});
