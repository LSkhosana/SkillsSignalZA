import { render, screen } from '@testing-library/react-native';

import { PAID_REPORT_SECTION_KEYS } from '@/services/api';
import { checkReportUnlock } from '@/services/flow';

import ReportScreen from '../../app/assessment/[assessmentId]/report';
import { REPORT_FIXTURE } from './fixtures';

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

jest.mock('@/services/flow', () => ({
  checkReportUnlock: jest.fn(),
}));

describe('report screen authorization', () => {
  beforeEach(() => {
    mockReplace.mockClear();
    (checkReportUnlock as jest.Mock).mockReset();
  });

  it('does not render paid report content for the wrong owner', async () => {
    (checkReportUnlock as jest.Mock).mockResolvedValue({
      status: 'blocked',
      code: 'ASSESSMENT_NOT_OWNED',
      message: 'This assessment is not available on this account.',
    });
    await render(<ReportScreen />);
    expect(await screen.findByTestId('report-unavailable')).toBeTruthy();
    expect(screen.queryByTestId('full-report')).toBeNull();
    expect(screen.queryByText('Areas to strengthen')).toBeNull();
    expect(screen.queryByText('Five priority actions')).toBeNull();
    for (const key of PAID_REPORT_SECTION_KEYS) {
      expect(screen.queryByTestId(`preview-absent-${key}`)).toBeNull();
    }
    expect(checkReportUnlock).toHaveBeenCalledWith('a-test-1', { accessToken: 'tok' });
  });

  it('renders the canonical report only after a backend 200', async () => {
    (checkReportUnlock as jest.Mock).mockResolvedValue({
      status: 'unlocked',
      report: REPORT_FIXTURE,
    });
    await render(<ReportScreen />);
    expect(await screen.findByTestId('full-report')).toBeTruthy();
    expect(screen.getByTestId('report-material-gaps')).toHaveTextContent(/Areas to strengthen/);
  });
});
