import { render, screen } from '@testing-library/react-native';

import PaymentScreen from '../../app/assessment/[assessmentId]/payment';

jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  return {
    useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
    useLocalSearchParams: () => ({ assessmentId: 'a-test-1' }),
    Link: ({ children }: { children: unknown }) => React.createElement(Text, null, children),
  };
});

jest.mock('@/services/auth/provider', () => ({
  useAuth: () => ({
    status: 'signed_in',
    user: { id: 'user-1', email: 'a@b.test' },
    accessToken: 'tok',
    signOut: jest.fn(),
  }),
}));

jest.mock('@/services/auth', () => ({
  getAccessToken: jest.fn(async () => 'tok'),
}));

jest.mock('@/services/checkout/paystack', () => ({
  openPaystackCheckout: jest.fn(async () => 'opened'),
}));

jest.mock('@/services/flow', () => ({
  continueAfterAuthentication: jest.fn(async () => ({ status: 'claimed' })),
  startCheckout: jest.fn(async () => ({
    status: 'payment_initialized',
    authorizationUrl: 'https://checkout.paystack.com/test-session',
  })),
  checkReportUnlock: jest.fn(async () => ({ status: 'locked' })),
}));

describe('payment waiting state', () => {
  it('shows waiting copy and a manual check-payment action', async () => {
    await render(<PaymentScreen />);
    expect(await screen.findByTestId('payment-waiting')).toHaveTextContent(/Waiting for payment/);
    expect(screen.getByTestId('check-payment')).toBeTruthy();
    expect(screen.getByText(/does not start another checkout/i)).toBeTruthy();
    await screen.unmount();
  });
});
