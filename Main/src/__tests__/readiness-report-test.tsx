import { fireEvent, render, screen } from '@testing-library/react-native';
import { AccessibilityInfo } from 'react-native';

import { ReadinessReportView } from '@/components/readiness-report-view';
import { ReportSkeleton } from '@/components/system/skeleton';
import { overlappingStrengthIds } from '@/lib/readiness-report';

import { REPORT_FIXTURE } from './fixtures';

describe('full report sections', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });
  it('keeps score, track, diagnose, act and inspect sections from backend data', async () => {
    await render(<ReadinessReportView report={REPORT_FIXTURE} />);
    expect(screen.getByTestId('report-score-band')).toHaveTextContent(/72 \/ 100/);
    expect(screen.getByTestId('report-score-band')).toHaveTextContent(/Developing application readiness/);
    expect(screen.getByTestId('report-track-meta')).toHaveTextContent(/Software Engineering/);
    expect(screen.getByTestId('report-benchmark')).toHaveTextContent(/does not predict hiring outcomes/);
    expect(screen.getByTestId('report-strongest')).toHaveTextContent(/Applied build/);
    expect(screen.getByTestId('report-priority-gap')).toHaveTextContent(/Evidence depth/);
    expect(screen.getByTestId('report-category-breakdown')).toHaveTextContent(/Applied build/);
    expect(screen.getByTestId('report-strengths')).toHaveTextContent(/Build evidence/);
    expect(screen.getByTestId('report-material-gaps')).toHaveTextContent(/Areas to strengthen/);
    expect(screen.queryByText('Material gaps')).toBeNull();
    expect(screen.getByTestId('report-overlap-note')).toHaveTextContent(/overlap is expected/);
    expect(screen.getByTestId('report-priority-actions')).toHaveTextContent(
      /Add a production-shaped walkthrough of one shipped project/,
    );
    expect(screen.getByTestId('report-project-recommendation')).toHaveTextContent(/Service health dashboard/);
    expect(screen.getByTestId('report-criterion-breakdown')).toHaveTextContent(/Detailed criterion breakdown/);
  });

  it('preserves backend priority-action order without re-ranking', async () => {
    await render(<ReadinessReportView report={REPORT_FIXTURE} />);
    const actions = REPORT_FIXTURE.priority_actions.map((row) => row.candidate_instruction);
    expect(actions).toHaveLength(5);
    expect(screen.getByTestId('priority-action-1')).toHaveTextContent(/production-shaped walkthrough/);
    expect(screen.getByTestId('priority-action-2')).toHaveTextContent(/trade-off that shaped/);
    expect(screen.getByTestId('priority-action-3')).toHaveTextContent(/tests that cover the main failure path/);
    expect(screen.getByTestId('priority-action-4')).toHaveTextContent(/run the project locally/);
    expect(screen.getByTestId('priority-action-5')).toHaveTextContent(/original problem statement/);
  });

  it('labels overlapping strength and gap without mutating source rows', async () => {
    const original = REPORT_FIXTURE.material_gaps.map((row) => row.criterion_id);
    await render(<ReadinessReportView report={REPORT_FIXTURE} />);
    expect(overlappingStrengthIds(REPORT_FIXTURE.strengths, REPORT_FIXTURE.material_gaps).has('se-evidence-depth')).toBe(
      true,
    );
    expect(screen.getByTestId('report-material-gaps')).toHaveTextContent(/also listed as a strength/);
    expect(REPORT_FIXTURE.material_gaps.map((row) => row.criterion_id)).toEqual(original);
    expect(REPORT_FIXTURE.strengths).toHaveLength(2);
  });

  it('keeps criterion groups collapsed until opened', async () => {
    await render(<ReadinessReportView report={REPORT_FIXTURE} />);
    expect(screen.queryByText('Shipped project evidence is visible.')).toBeNull();
    expect(screen.getByTestId('criterion-group-applied_build').props.accessibilityState.expanded).toBe(false);
    await fireEvent.press(screen.getByTestId('criterion-group-applied_build'));
    expect(screen.getByText('Shipped project evidence is visible.')).toBeTruthy();
    expect(screen.getByTestId('criterion-group-applied_build').props.accessibilityState.expanded).toBe(true);
  });

  it('keeps reduced-motion category bars determinate', async () => {
    jest.spyOn(AccessibilityInfo, 'isReduceMotionEnabled').mockResolvedValue(true);
    jest.spyOn(AccessibilityInfo, 'addEventListener').mockReturnValue({ remove: jest.fn() } as never);
    await render(<ReadinessReportView report={REPORT_FIXTURE} />);
    expect(screen.getByLabelText('Applied build: 18 / 20').props.accessibilityValue).toEqual({
      min: 0,
      max: 100,
      now: 90,
    });
  });

  it('preserves report skeleton geometry for the flagship layout', async () => {
    await render(<ReportSkeleton />);
    expect(screen.getByLabelText('Loading report').props.accessibilityState).toEqual({ busy: true });
  });
});
