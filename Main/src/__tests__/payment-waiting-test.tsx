import { fireEvent, render, screen } from '@testing-library/react-native';

import { checkReportUnlock, continueAfterAuthentication, loadPendingAssessment, startCheckout } from '@/services/flow';
import { openPaystackCheckout } from '@/services/checkout/paystack';

import PaymentScreen from '../../app/assessment/[assessmentId]/payment';

const mockReplace = jest.fn();

jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  return {
    useRouter: () => ({ push: jest.fn(), replace: mockReplace }),
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
  startCheckout: jest.fn(),
  checkReportUnlock: jest.fn(),
  loadPendingAssessment: jest.fn(async () => ({
    assessment_id: 'a-test-1',
    preview: { track_label: 'Software Engineering' },
    claimed: true,
  })),
}));

describe('payment waiting state', () => {
  beforeEach(() => {
    mockReplace.mockClear();
    (startCheckout as jest.Mock).mockReset();
    (checkReportUnlock as jest.Mock).mockReset();
    (openPaystackCheckout as jest.Mock).mockReset();
    (startCheckout as jest.Mock).mockResolvedValue({
      status: 'payment_initialized',
      authorizationUrl: 'https://checkout.paystack.com/test-session',
    });
    (checkReportUnlock as jest.Mock).mockResolvedValue({ status: 'locked' });
    (continueAfterAuthentication as jest.Mock).mockResolvedValue({ status: 'claimed' });
    (loadPendingAssessment as jest.Mock).mockResolvedValue({
      assessment_id: 'a-test-1',
      preview: { track_label: 'Software Engineering' },
      claimed: true,
    });
  });

  it('shows an order summary and does not auto-start checkout', async () => {
    const view = await render(<PaymentScreen />);
    expect(await screen.findByTestId('order-summary')).toBeTruthy();
    expect(screen.getAllByText(/Readiness Report/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Track: Software Engineering/)).toBeTruthy();
    expect(screen.getByText(/Amount: R159/)).toBeTruthy();
    expect(screen.getAllByText(/one-time payment/i).length).toBeGreaterThan(0);
    expect(screen.getByTestId('continue-payment')).toBeTruthy();
    expect(screen.getByTestId('check-payment')).toBeTruthy();
    expect(screen.getByText(/does not start another checkout/i)).toBeTruthy();
    expect(startCheckout).not.toHaveBeenCalled();
    expect(openPaystackCheckout).not.toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
    await view.unmount();
  });

  it('starts checkout once, then waits for backend confirmation', async () => {
    const view = await render(<PaymentScreen />);
    await screen.findByTestId('order-summary');
    await fireEvent.press(screen.getByTestId('continue-payment'));
    expect(startCheckout).toHaveBeenCalledTimes(1);
    expect(await screen.findByTestId('payment-waiting')).toHaveTextContent(/Waiting for payment/);
    expect(screen.getByTestId('open-checkout')).toBeTruthy();
    await fireEvent.press(screen.getByTestId('check-payment'));
    expect(checkReportUnlock).toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
    expect(screen.queryByText(/Server\//)).toBeNull();
    await view.unmount();
  });

  it('unlocks only after backend-confirmed entitlement', async () => {
    const view = await render(<PaymentScreen />);
    await screen.findByTestId('order-summary');
    await fireEvent.press(screen.getByTestId('continue-payment'));
    await screen.findByTestId('payment-waiting');
    expect(mockReplace).not.toHaveBeenCalled();
    (checkReportUnlock as jest.Mock).mockResolvedValueOnce({
      status: 'unlocked',
      report: { schema_version: 'readiness.report.v1' },
    });
    await fireEvent.press(screen.getByTestId('check-payment'));
    expect(mockReplace).toHaveBeenCalledWith('/assessment/a-test-1/report');
    await view.unmount();
  });
});
