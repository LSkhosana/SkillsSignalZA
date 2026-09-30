import { render, screen } from '@testing-library/react-native';

import { GlobalFooter } from '@/components/system/global-footer';
import { SelectField, TextField } from '@/components/system/fields';
import { LEGAL_PATHS, MARKETING_FOOTER_LINKS, Routes } from '@/lib/routes';
import { PRIVACY_COPY, REFUNDS_COPY, SUPPORT_COPY, TERMS_COPY } from '@/lib/legal-copy';

import MapPackScreen from '../../app/map-pack';
import NotFoundScreen from '../../app/+not-found';
import PrivacyScreen from '../../app/privacy';
import RefundsScreen from '../../app/refunds';
import SupportScreen from '../../app/support';
import TermsScreen from '../../app/terms';

jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  return {
    useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
    Link: ({ children, href }: { children: unknown; href: unknown }) =>
      React.createElement(Text, { accessibilityRole: 'link', href: String(href) }, children),
    Stack: { Screen: () => null },
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

const invented = /90 days|30 days|ISO 27001|SOC 2|10,000 customers|we delete automatically|guaranteed refund|within 7 days|we reply within/i;

describe('legal and trust surfaces', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders Privacy without inventing a retention period', async () => {
    await render(<PrivacyScreen />);
    expect(screen.getByTestId('privacy-screen')).toBeTruthy();
    expect(screen.getByText('What you submit')).toBeTruthy();
    expect(screen.getByTestId('privacy-screen-unpublished')).toHaveTextContent(/has not published a retention period/i);
  });

  it('renders Terms from current product behaviour', async () => {
    await render(<TermsScreen />);
    expect(screen.getByTestId('terms-screen')).toHaveTextContent(/one-time R159/i);
    expect(screen.getByTestId('terms-screen')).toHaveTextContent(/does not make hiring decisions/i);
  });

  it('renders Refunds without a promised refund window', async () => {
    await render(<RefundsScreen />);
    expect(screen.getByTestId('refunds-screen-unpublished')).toHaveTextContent(/does not promise a refund/i);
    expect(screen.getByTestId('refunds-screen')).toHaveTextContent(/Do not make another payment/i);
  });

  it('renders Support without a fabricated contact address', async () => {
    await render(<SupportScreen />);
    expect(screen.getByTestId('support-screen-unpublished')).toHaveTextContent(/not published/i);
    expect(screen.getByTestId('support-screen')).toHaveTextContent(/Do not send passwords/i);
  });

  it('wires the shared footer to the legal routes', async () => {
    await render(<GlobalFooter />);
    expect(screen.getByText('Privacy').props.href).toBe(String(Routes.privacy));
    expect(screen.getByText('Terms').props.href).toBe(String(Routes.terms));
    expect(screen.getByText('Refund policy').props.href).toBe(String(Routes.refunds));
    expect(screen.getByText('Support').props.href).toBe(String(Routes.support));
  });

  it('points marketing footer legal items at the same customer routes', () => {
    const legal = MARKETING_FOOTER_LINKS.filter((link) =>
      ['Privacy', 'Terms', 'Refunds', 'Support'].includes(link.label),
    );
    expect(legal.map((link) => link.href)).toEqual([...LEGAL_PATHS]);
  });

  it('keeps Career Map Pack as an honest placeholder', async () => {
    await render(<MapPackScreen />);
    expect(screen.getByTestId('map-pack-placeholder')).toHaveTextContent(/not part of this release/i);
    expect(screen.queryByText(/buy now|download the pack/i)).toBeNull();
  });

  it('explains unknown routes without charging or scoring', async () => {
    await render(<NotFoundScreen />);
    expect(screen.getByTestId('not-found-state')).toHaveTextContent(/not part of SkillSignalZA/i);
    expect(screen.getByLabelText('Go to start')).toBeTruthy();
  });

  it('does not invent retention, refund windows or contact addresses in copy modules', () => {
    const blob = JSON.stringify([PRIVACY_COPY, TERMS_COPY, REFUNDS_COPY, SUPPORT_COPY]);
    expect(blob).not.toMatch(invented);
    expect(blob).not.toMatch(/@[a-z0-9.-]+\.(com|za)\b/i);
  });
});

describe('form accessibility associations', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('keeps a field error with the control and without colour-only meaning', async () => {
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
    expect(screen.getByTestId('evidence-link-error')).toHaveTextContent('Enter a full public URL.');
  });

  it('exposes radio checked state in words and semantics', async () => {
    await render(
      <SelectField
        label="Track"
        value="software_engineering"
        onChange={jest.fn()}
        options={[
          { value: 'software_engineering', label: 'Software Engineering' },
          { value: 'data_analytics', label: 'Data Analytics' },
        ]}
        testID="track"
      />,
    );
    expect(screen.getByLabelText('Software Engineering').props.accessibilityState.checked).toBe(true);
    expect(screen.getByLabelText('Software Engineering')).toHaveTextContent(/Selected:/);
    expect(screen.getByLabelText('Data Analytics').props.accessibilityState.checked).toBe(false);
  });
});
