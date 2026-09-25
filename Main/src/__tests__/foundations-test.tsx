import { fireEvent, render, screen } from '@testing-library/react-native';
import { AccessibilityInfo, Text } from 'react-native';

import { ScreenShell } from '@/components/screen-shell';
import { AccountMenu } from '@/components/system/account-menu';
import { AppHeader } from '@/components/system/app-header';
import { Button } from '@/components/system/button';
import { PageState, ToastProvider, useToast } from '@/components/system/feedback';
import { TextField } from '@/components/system/fields';
import { Accordion, ProgressBar } from '@/components/system/surfaces';
import { PreviewSkeleton } from '@/components/system/skeleton';
import { WorkspaceShell } from '@/components/system/workspace-shell';
import { useReducedMotion } from '@/hooks/use-reduced-motion';
import { Colors } from '@/theme';

const mockPush = jest.fn();
const mockSignOut = jest.fn();
const mockRouterState = { pathname: '/' };
const mockAuth = {
  status: 'signed_out' as 'signed_out' | 'signed_in' | 'loading',
  user: null as { id: string; email: string | null } | null,
  accessToken: null as string | null,
  signOut: mockSignOut,
};

jest.mock('expo-router', () => {
  const React = require('react');
  const { Text: NativeText } = require('react-native');
  return {
    usePathname: () => mockRouterState.pathname,
    useRouter: () => ({ push: mockPush, replace: jest.fn() }),
    Link: ({ children }: { children: unknown }) => React.createElement(NativeText, null, children),
  };
});

jest.mock('@/services/auth/provider', () => ({
  useAuth: () => mockAuth,
}));

function flatStyle(style: unknown): Record<string, unknown> {
  if (Array.isArray(style)) {
    return Object.assign({}, ...style.flat(6).filter(Boolean).map((item) => flatStyle(item)));
  }
  if (style && typeof style === 'object') {
    return style as Record<string, unknown>;
  }
  return {};
}

function ReducedMotionProbe() {
  const reduced = useReducedMotion();
  return <Text>{reduced ? 'reduced-motion' : 'motion-on'}</Text>;
}

function ToastProbe() {
  const { showToast } = useToast();
  return <Button label="Show notice" onPress={() => showToast('Report saved')} />;
}

describe('launch foundations', () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockSignOut.mockClear();
    mockRouterState.pathname = '/';
    mockAuth.status = 'signed_out';
    mockAuth.user = null;
  });

  it('uses the landing Excel-green paper palette', () => {
    expect(Colors.light.accent).toBe('#217346');
    expect(Colors.light.background).toBe('#F7F6F0');
    expect(Colors.light.text).toBe('#101413');
    expect(Colors.light.border).toBe('#D7D9D3');
    expect(Colors.light.muted).toBe('#666D69');
    expect(Colors.dark.accent).toBe(Colors.light.accent);
  });

  it('keeps primary controls square with a 44px target', async () => {
    await render(<Button label="Continue" onPress={jest.fn()} testID="continue" />);
    const button = screen.getByTestId('continue');
    const rawStyle = button.props.style;
    const style = flatStyle(typeof rawStyle === 'function' ? rawStyle({ pressed: false }) : rawStyle);
    expect(style.minHeight).toBe(44);
    expect(style.borderRadius).toBe(0);
    expect(button.props.accessibilityState).toEqual({ disabled: false, busy: false });
  });

  it('associates a field label and keeps the error with the field', async () => {
    await render(
      <TextField
        label="Evidence link"
        value="notaurl"
        onChangeText={jest.fn()}
        error="Enter a full public URL."
        testID="evidence-link"
      />,
    );
    expect(screen.getByLabelText('Evidence link')).toBeTruthy();
    expect(screen.getByText('Enter a full public URL.')).toBeTruthy();
  });

  it('answers a route failure in four parts', async () => {
    await render(
      <PageState
        happened="That assessment could not be found."
        meaning="The preview was not opened."
        consequence="Nothing was charged."
        action={<Text>Try again</Text>}
      />,
    );
    expect(screen.getByText('What happened')).toBeTruthy();
    expect(screen.getByText('That assessment could not be found.')).toBeTruthy();
    expect(screen.getByText('What this means')).toBeTruthy();
    expect(screen.getByText('The preview was not opened.')).toBeTruthy();
    expect(screen.getByText('Charged or lost')).toBeTruthy();
    expect(screen.getByText('Nothing was charged.')).toBeTruthy();
    expect(screen.getByText('Try again')).toBeTruthy();
  });

  it('uses a masked account menu instead of a raw email', async () => {
    mockAuth.status = 'signed_in';
    mockAuth.user = { id: 'user-1', email: 'candidate@example.com' };
    await render(<AccountMenu />);
    expect(screen.queryByText('candidate@example.com')).toBeNull();
    await fireEvent.press(screen.getByTestId('account-menu-trigger'));
    expect(screen.getByText('c•••@example.com')).toBeTruthy();
    expect(screen.getByText('My Reports')).toBeTruthy();
    expect(screen.getByText('Start new assessment')).toBeTruthy();
    expect(screen.getByText('Account')).toBeTruthy();
    await fireEvent.press(screen.getByLabelText('Sign out'));
    expect(mockSignOut).toHaveBeenCalled();
  });

  it('offers sign-in from the marketing header', async () => {
    await render(<AppHeader />);
    await fireEvent.press(screen.getByLabelText('Sign in'));
    expect(mockPush).toHaveBeenCalledWith('/sign-in');
    expect(screen.getByTestId('header-start-assessment')).toBeTruthy();
    expect(screen.getByText('Career Map Pack')).toBeTruthy();
  });

  it('expands an accordion without relying on colour alone', async () => {
    await render(
      <Accordion title="Criterion detail" testID="criterion">
        <Text>Anchor evidence</Text>
      </Accordion>,
    );
    expect(screen.queryByText('Anchor evidence')).toBeNull();
    await fireEvent.press(screen.getByTestId('criterion'));
    expect(screen.getByText('Anchor evidence')).toBeTruthy();
    expect(screen.getByTestId('criterion').props.accessibilityState.expanded).toBe(true);
  });

  it('exposes a determinate score bar and a preview skeleton', async () => {
    await render(
      <>
        <ProgressBar label="Tools" value={55} testID="tools-bar" />
        <PreviewSkeleton />
      </>,
    );
    expect(screen.getByLabelText('Tools').props.accessibilityValue).toEqual({
      min: 0,
      max: 100,
      now: 55,
    });
    expect(screen.getByLabelText('Loading preview').props.accessibilityState).toEqual({ busy: true });
  });

  it('keeps the workspace and its rail in one shell', async () => {
    await render(
      <WorkspaceShell rail={<Text>Free preview note</Text>} testID="workspace">
        <Text>Assessment form</Text>
      </WorkspaceShell>,
    );
    expect(screen.getByText('Assessment form')).toBeTruthy();
    expect(screen.getByText('Free preview note')).toBeTruthy();
  });

  it('places shared footer links on application screens', async () => {
    await render(
      <ScreenShell title="Sign in">
        <Text>Email and password</Text>
      </ScreenShell>,
    );
    expect(screen.getByText('Privacy')).toBeTruthy();
    expect(screen.getByText('Terms')).toBeTruthy();
    expect(screen.getByText('Refund policy')).toBeTruthy();
    expect(screen.getByText('Support')).toBeTruthy();
    expect(screen.getByText('Sign in')).toBeTruthy();
  });

  it('shows a transient toast without shifting the page title', async () => {
    await render(
      <ToastProvider>
        <Text>Stable title</Text>
        <ToastProbe />
      </ToastProvider>,
    );
    await fireEvent.press(screen.getByLabelText('Show notice'));
    expect(await screen.findByText('Report saved')).toBeTruthy();
    expect(screen.getByText('Stable title')).toBeTruthy();
  });

  it('follows the reduced-motion setting', async () => {
    jest.spyOn(AccessibilityInfo, 'isReduceMotionEnabled').mockResolvedValue(true);
    jest.spyOn(AccessibilityInfo, 'addEventListener').mockReturnValue({ remove: jest.fn() } as never);
    await render(<ReducedMotionProbe />);
    expect(await screen.findByText('reduced-motion')).toBeTruthy();
  });
});
