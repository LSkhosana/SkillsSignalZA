import { render, screen } from '@testing-library/react-native';

import { PreviewSummary } from '@/components/preview-summary';
import { PAID_REPORT_SECTION_KEYS } from '@/services/api';

import { PREVIEW_FIXTURE } from './fixtures';

describe('preview rendering', () => {
  it('renders free preview fields and no paid sections', async () => {
    await render(<PreviewSummary preview={PREVIEW_FIXTURE} />);
    expect(screen.getByTestId('preview-score')).toHaveTextContent(/72 \/ 100/);
    expect(screen.getByTestId('preview-band')).toHaveTextContent(/Developing application readiness/);
    expect(screen.getByTestId('preview-strongest')).toHaveTextContent(/Applied build/);
    expect(screen.getByTestId('preview-gap')).toHaveTextContent(/Evidence depth/);
    expect(screen.queryByText('Category breakdown')).toBeNull();
    expect(screen.queryByText('Priority actions')).toBeNull();
    expect(screen.queryByText('Project recommendation')).toBeNull();
    expect(screen.queryByText('Criterion breakdown')).toBeNull();
    for (const key of PAID_REPORT_SECTION_KEYS) {
      expect(screen.getByTestId(`preview-absent-${key}`)).toBeTruthy();
    }
  });
});
