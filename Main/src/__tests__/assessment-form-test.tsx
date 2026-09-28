import { fireEvent, render, screen } from '@testing-library/react-native';
import * as DocumentPicker from 'expo-document-picker';

import { validatePickedCv } from '@/lib/cv';
import { ApiError, submitAssessment } from '@/services/api';

import NewAssessmentScreen from '../../app/assessment/new';

const mockReplace = jest.fn();

jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  return {
    useRouter: () => ({ push: jest.fn(), replace: mockReplace }),
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

jest.mock('@/services/flow', () => ({
  savePendingAssessment: jest.fn(async () => undefined),
  saveClaimToken: jest.fn(async () => undefined),
  continueAfterAuthentication: jest.fn(async () => ({ status: 'needs_auth' })),
}));

jest.mock('@/services/api', () => {
  const actual = jest.requireActual('@/services/api');
  return {
    ...actual,
    submitAssessment: jest.fn(),
  };
});

jest.mock('expo-document-picker', () => ({
  getDocumentAsync: jest.fn(async () => ({
    canceled: false,
    assets: [{ uri: 'file:///tmp/notes.txt', name: 'notes.txt', mimeType: 'text/plain', size: 12 }],
  })),
}));

const submitAssessmentMock = submitAssessment as jest.MockedFunction<typeof submitAssessment>;

function validCvPicker() {
  (DocumentPicker.getDocumentAsync as jest.Mock).mockResolvedValueOnce({
    canceled: false,
    assets: [{ uri: 'file:///tmp/cv.pdf', name: 'cv.pdf', mimeType: 'application/pdf', size: 1024 }],
  });
}

describe('assessment form', () => {
  beforeEach(() => {
    mockReplace.mockClear();
    submitAssessmentMock.mockReset();
  });

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

  it('keeps submit disabled until a valid CV exists and blocks a malformed link', async () => {
    await render(<NewAssessmentScreen />);
    expect(screen.getByTestId('submit-assessment').props.accessibilityState.disabled).toBe(true);
    await fireEvent.press(screen.getByTestId('add-link'));
    await fireEvent.changeText(screen.getByTestId('link-url-0'), 'notaurl');
    expect(screen.getByText('Enter a full public URL starting with https://.')).toBeTruthy();
    validCvPicker();
    await fireEvent.press(screen.getByTestId('pick-cv'));
    expect(screen.getByTestId('submit-assessment').props.accessibilityState.disabled).toBe(true);
    await fireEvent.press(screen.getByTestId('submit-assessment'));
    expect(submitAssessmentMock).not.toHaveBeenCalled();
    expect(screen.queryByTestId('unlock-report')).toBeNull();
  });

  it('submits once while the request is in flight', async () => {
    let resolveSubmit: (value: Awaited<ReturnType<typeof submitAssessment>>) => void = () => undefined;
    submitAssessmentMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSubmit = resolve;
        }),
    );
    await render(<NewAssessmentScreen />);
    validCvPicker();
    await fireEvent.press(screen.getByTestId('pick-cv'));
    await fireEvent.press(screen.getByTestId('submit-assessment'));
    await fireEvent.press(screen.getByTestId('submit-assessment'));
    expect(submitAssessmentMock).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('processing-state')).toBeTruthy();
    expect(screen.getByTestId('processing-state')).not.toHaveTextContent(/%/);
    expect(screen.getByTestId('form-track-data_analytics').props.accessibilityState.disabled).toBe(true);
    resolveSubmit({
      ok: false,
      status: 503,
      error: new ApiError({
        message: 'down',
        status: 503,
        code: 'ASSESSMENT_SERVICE_UNAVAILABLE',
      }),
    });
    expect(await screen.findByTestId('outcome-service-failure')).toBeTruthy();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it('does not open payment after review or an unscorable result', async () => {
    submitAssessmentMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      data: {
        schema_version: 'anonymous.assessment.v1',
        state: 'REVIEW_REQUIRED',
        assessment_id: 'a-review',
        run_id: 'r-review',
        access_state: null,
        claim_token: null,
        preview: null,
        error_code: 'REVIEW_REQUIRED',
      },
    });
    await render(<NewAssessmentScreen />);
    validCvPicker();
    await fireEvent.press(screen.getByTestId('pick-cv'));
    await fireEvent.press(screen.getByTestId('submit-assessment'));
    expect(await screen.findByTestId('outcome-review-required')).toBeTruthy();
    expect(screen.queryByTestId('submit-assessment')).toBeNull();
    expect(screen.queryByText(/Unlock full report/)).toBeNull();
    expect(mockReplace).not.toHaveBeenCalled();

    submitAssessmentMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      data: {
        schema_version: 'anonymous.assessment.v1',
        state: 'NOT_SCORABLE',
        assessment_id: 'a-gap',
        run_id: 'r-gap',
        access_state: null,
        claim_token: null,
        preview: null,
        error_code: 'NOT_SCORABLE',
      },
    });
    await fireEvent.press(screen.getByTestId('reset-assessment'));
    await fireEvent.press(screen.getByTestId('submit-assessment'));
    expect(await screen.findByTestId('outcome-not-scorable')).toBeTruthy();
    expect(mockReplace).not.toHaveBeenCalled();
    expect(screen.queryByText(/Unlock full report/)).toBeNull();
  });
});
