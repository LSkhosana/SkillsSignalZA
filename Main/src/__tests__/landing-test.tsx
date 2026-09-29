import { fireEvent, render, screen } from '@testing-library/react-native';

import { LEGAL_PATHS, MARKETING_FOOTER_LINKS } from '@/lib/routes';

import LandingScreen from '../../app/index';

const mockPush = jest.fn();

jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  return {
    useRouter: () => ({ push: mockPush, replace: jest.fn() }),
    Link: ({ children }: { children: unknown }) => React.createElement(Text, null, children),
  };
});

jest.mock('@/services/auth/provider', () => ({
  useAuth: () => ({
    status: 'signed_out',
    user: null,
    accessToken: null,
    signOut: jest.fn(),
  }),
}));

describe('landing screen', () => {
  beforeEach(() => {
    mockPush.mockClear();
  });

  it('starts an assessment for the selected track', async () => {
    await render(<LandingScreen />);
    await fireEvent.press(screen.getByTestId('track-data_analytics'));
    await fireEvent.press(screen.getByTestId('start-assessment'));
    expect(mockPush).toHaveBeenCalledWith({
      pathname: '/assessment/new',
      params: { track: 'data_analytics' },
    });
  });

  it('discloses the R159 paid report before checkout', async () => {
    await render(<LandingScreen />);
    expect(screen.getByText(/full Readiness Report costs R159/i)).toBeTruthy();
    expect(screen.getByText(/does not estimate hiring probability/i)).toBeTruthy();
  });

  it('points marketing legal links at real routes', () => {
    expect([...LEGAL_PATHS]).toEqual(['/privacy', '/terms', '/refunds', '/support']);
    expect(
      MARKETING_FOOTER_LINKS.filter((link) => ['Privacy', 'Terms', 'Refunds', 'Support'].includes(link.label)).map(
        (link) => link.href,
      ),
    ).toEqual([...LEGAL_PATHS]);
  });
});
