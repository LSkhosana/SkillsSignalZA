import { fireEvent, render, screen } from '@testing-library/react-native';

import { validatePickedCv } from '@/lib/cv';

import NewAssessmentScreen from '../../app/assessment/new';

jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  return {
    useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
    useLocalSearchParams: () => ({ track: 'software_engineering' }),
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

jest.mock('@/services/auth', () => ({
  getAccessToken: jest.fn(async () => null),
}));

jest.mock('expo-document-picker', () => ({
  getDocumentAsync: jest.fn(async () => ({
    canceled: false,
    assets: [{ uri: 'file:///tmp/notes.txt', name: 'notes.txt', mimeType: 'text/plain', size: 12 }],
  })),
}));

describe('assessment form', () => {
  it('keeps the selected track visible', async () => {
    await render(<NewAssessmentScreen />);
    expect(screen.getByText(/Track: Software Engineering/)).toBeTruthy();
    await fireEvent.press(screen.getByTestId('form-track-data_analytics'));
    expect(screen.getByText(/Track: Data Analytics/)).toBeTruthy();
  });

  it('rejects unsupported CV types', async () => {
    await render(<NewAssessmentScreen />);
    await fireEvent.press(screen.getByTestId('pick-cv'));
    expect(await screen.findByText('Please choose a PDF or DOCX file.')).toBeTruthy();
  });

  it('validates type and size as a convenience only', () => {
    expect(
      validatePickedCv({
        uri: 'file:///cv.pdf',
        name: 'cv.pdf',
        mimeType: 'application/pdf',
        size: 11 * 1024 * 1024,
      }),
    ).toBe('The CV must be 10 MB or smaller.');
    expect(
      validatePickedCv({
        uri: 'file:///cv.pdf',
        name: 'cv.pdf',
        mimeType: 'application/pdf',
        size: 1024,
      }),
    ).toBeNull();
  });
});
