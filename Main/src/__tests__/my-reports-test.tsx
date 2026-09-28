import { fireEvent, render, screen } from '@testing-library/react-native';

import { listOwnedAssessments } from '@/services/api';
import { loadPendingAssessment } from '@/services/flow';

import ReportsScreen from '../../app/reports';
import { LISTED_SUMMARIES as SUMMARIES, PREVIEW_SUMMARY, UNLOCKED_SUMMARY } from './fixtures';

const mockReplace = jest.fn();
const mockPush = jest.fn();
const mockAuth = {
  status: 'signed_in' as 'signed_in' | 'signed_out' | 'loading',
  user: { id: 'user-1', email: 'a@b.test' } as { id: string; email: string | null } | null,
};

jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  return {
    useRouter: () => ({ push: mockPush, replace: mockReplace }),
    Link: ({ children }: { children: unknown }) => React.createElement(Text, null, children),
  };
});

jest.mock('@/services/auth/provider', () => ({
  useAuth: () => mockAuth,
}));

jest.mock('@/services/auth', () => ({
  getAccessToken: jest.fn(async () => 'tok-reports'),
}));

jest.mock('@/services/api', () => {
  const actual = jest.requireActual('@/services/api');
  return {
    ...actual,
    listOwnedAssessments: jest.fn(),
  };
});

jest.mock('@/services/flow', () => ({
  loadPendingAssessment: jest.fn(),
}));

describe('My Reports', () => {
  beforeEach(() => {
    mockReplace.mockClear();
    mockPush.mockClear();
    mockAuth.status = 'signed_in';
    mockAuth.user = { id: 'user-1', email: 'a@b.test' };
    (listOwnedAssessments as jest.Mock).mockReset();
    (loadPendingAssessment as jest.Mock).mockReset();
  });

  it('renders owned summaries from the authenticated list endpoint', async () => {
    (listOwnedAssessments as jest.Mock).mockResolvedValue({ ok: true, data: SUMMARIES, status: 200 });
    await render(<ReportsScreen />);
    expect(await screen.findByTestId('reports-list')).toBeTruthy();
    expect(screen.getByTestId('report-entry-a-test-1')).toHaveTextContent(/Software Engineering/);
    expect(screen.getByTestId('report-entry-a-test-1')).toHaveTextContent(/72 \/ 100/);
    expect(screen.getByTestId('report-entry-a-test-1')).toHaveTextContent(/Unlocked/);
    expect(screen.getByTestId('report-entry-a-test-2')).toHaveTextContent(/Not purchased/);
    expect(listOwnedAssessments).toHaveBeenCalledWith({ accessToken: 'tok-reports' });
    expect(loadPendingAssessment).not.toHaveBeenCalled();
    expect(screen.queryByText(/claim token/i)).toBeNull();
  });

  it('shows an empty state with a start-assessment CTA', async () => {
    (listOwnedAssessments as jest.Mock).mockResolvedValue({
      ok: true,
      data: { ...SUMMARIES, items: [] },
      status: 200,
    });
    await render(<ReportsScreen />);
    expect(await screen.findByTestId('reports-empty')).toBeTruthy();
    expect(screen.getByTestId('reports-start-assessment')).toBeTruthy();
  });

  it('shows the My Reports skeleton while the list is loading', async () => {
    let resolveList: (value: unknown) => void = () => undefined;
    (listOwnedAssessments as jest.Mock).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveList = resolve;
        }),
    );
    await render(<ReportsScreen />);
    expect(screen.getByLabelText('Loading reports').props.accessibilityState).toEqual({ busy: true });
    resolveList({ ok: true, data: { ...SUMMARIES, items: [] }, status: 200 });
    expect(await screen.findByTestId('reports-empty')).toBeTruthy();
  });

  it('shows a recovery PageState when the list API fails', async () => {
    (listOwnedAssessments as jest.Mock).mockResolvedValue({
      ok: false,
      status: 503,
      error: { code: 'SUMMARIES_SERVICE_UNAVAILABLE', message: 'down', status: 503 },
    });
    await render(<ReportsScreen />);
    expect(await screen.findByTestId('reports-unavailable')).toBeTruthy();
    expect(screen.getByTestId('reports-unavailable')).toHaveTextContent(/could not be loaded/i);
    expect(screen.getByTestId('reports-retry')).toBeTruthy();
  });

  it('opens the protected report route from an unlocked item', async () => {
    (listOwnedAssessments as jest.Mock).mockResolvedValue({
      ok: true,
      data: { ...SUMMARIES, items: [UNLOCKED_SUMMARY] },
      status: 200,
    });
    await render(<ReportsScreen />);
    await fireEvent.press(await screen.findByTestId('view-report-a-test-1'));
    expect(mockPush).toHaveBeenCalledWith('/assessment/a-test-1/report');
  });

  it('keeps a preview item locked and continues through payment', async () => {
    (listOwnedAssessments as jest.Mock).mockResolvedValue({
      ok: true,
      data: { ...SUMMARIES, items: [PREVIEW_SUMMARY] },
      status: 200,
    });
    await render(<ReportsScreen />);
    expect(await screen.findByTestId('report-entry-a-test-2')).toHaveTextContent(/Not purchased/);
    expect(screen.queryByTestId('view-report-a-test-2')).toBeNull();
    await fireEvent.press(screen.getByTestId('continue-unlock-a-test-2'));
    expect(mockPush).toHaveBeenCalledWith('/assessment/a-test-2/payment');
  });

  it('does not use local pending-assessment storage after a fresh login', async () => {
    (listOwnedAssessments as jest.Mock).mockResolvedValue({ ok: true, data: SUMMARIES, status: 200 });
    await render(<ReportsScreen />);
    await screen.findByTestId('reports-list');
    expect(loadPendingAssessment).not.toHaveBeenCalled();
    expect(listOwnedAssessments).toHaveBeenCalled();
  });

  it('sends expired sessions through auth resume to My Reports', async () => {
    (listOwnedAssessments as jest.Mock).mockResolvedValue({
      ok: false,
      status: 401,
      error: { code: 'AUTH_INVALID', message: 'expired', status: 401 },
    });
    await render(<ReportsScreen />);
    expect(await screen.findByTestId('reports-screen')).toBeTruthy();
    expect(mockReplace).toHaveBeenCalledWith({ pathname: '/session-expired', params: { next: 'reports' } });
  });
});
