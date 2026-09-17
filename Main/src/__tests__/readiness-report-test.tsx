import { render, screen } from '@testing-library/react-native';

import { ReadinessReportView } from '@/components/readiness-report-view';

import { REPORT_FIXTURE } from './fixtures';

describe('full report sections', () => {
  it('renders the major backend-supplied report sections in order', async () => {
    await render(<ReadinessReportView report={REPORT_FIXTURE} />);
    expect(screen.getByTestId('report-score-band')).toHaveTextContent(/72 \/ 100/);
    expect(screen.getByTestId('report-benchmark')).toHaveTextContent(/does not predict hiring outcomes/);
    expect(screen.getByTestId('report-strongest')).toHaveTextContent(/Applied build/);
    expect(screen.getByTestId('report-priority-gap')).toHaveTextContent(/Evidence depth/);
    expect(screen.getByTestId('report-category-breakdown')).toHaveTextContent(/Applied build/);
    expect(screen.getByTestId('report-strengths')).toHaveTextContent(/Build evidence/);
    expect(screen.getByTestId('report-material-gaps')).toHaveTextContent(/Evidence depth/);
    expect(screen.getByTestId('report-priority-actions')).toHaveTextContent(
      /Add a production-shaped walkthrough of one shipped project/,
    );
    expect(screen.getByTestId('report-project-recommendation')).toHaveTextContent(/Service health dashboard/);
    expect(screen.getByTestId('report-criterion-breakdown')).toHaveTextContent(/Build evidence/);
  });
});
