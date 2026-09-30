import { Platform, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { EditionMasthead } from '@/components/edition-masthead';
import { Accordion } from '@/components/system/surfaces';
import { formatCustomerDate } from '@/lib/assessment-summaries';
import {
  evidenceNoteForCategory,
  evidenceNoteForCriterion,
  gapsOutsideStrengths,
  groupCriteriaByCategory,
  openPointsOnStrength,
  overlappingStrengthIds,
} from '@/lib/readiness-report';
import type { ReadinessReport } from '@/services/api';
import { FontFamily, Layout, Palette } from '@/theme/tokens';

type ReadinessReportViewProps = {
  report: ReadinessReport;
};

function webClass(className: string) {
  return Platform.OS === 'web' ? { className } : {};
}

export function ReadinessReportView({ report }: ReadinessReportViewProps) {
  const { width } = useWindowDimensions();
  const columns = width >= Layout.tablet;
  const summary = report.score_summary;
  const overlapIds = overlappingStrengthIds(report.strengths, report.material_gaps);
  const remainingGaps = gapsOutsideStrengths(report.strengths, report.material_gaps);
  const groups = groupCriteriaByCategory(report.criterion_breakdown);
  const strongestQuote = evidenceNoteForCategory(
    summary.strongest_area.category_id,
    report.strengths,
    report.criterion_breakdown,
  );
  const gapQuote = summary.priority_gap
    ? evidenceNoteForCriterion(report.criterion_breakdown, summary.priority_gap.criterion_id)
    : null;

  return (
    <View {...webClass('ss-edition')} style={styles.stack} testID="full-report">
      <EditionMasthead
        dateline={`${report.track_label} · ${formatCustomerDate(report.assessed_at)}`}
        score={summary.final_score}
        scoreMax={summary.score_max}
        bandLabel={summary.band_label}
        bandStatement={summary.band_statement}
        scopeStatement={report.benchmark.scope_statement}
        disclaimer={report.benchmark.disclaimer}
        testID="report-score-band"
        disclaimerTestID="report-benchmark"
      />
      <Text style={styles.track} testID="report-track-meta">
        {report.track_label}
      </Text>

      <View style={[styles.columns, columns ? styles.columnsWide : null]}>
        <View style={styles.column} testID="report-category-breakdown">
          <Text style={styles.kicker}>Category scores</Text>
          {report.category_breakdown.map((row) => (
            <View
              key={row.category_id}
              accessibilityRole="progressbar"
              accessibilityLabel={`${row.label}: ${row.score} / ${row.max_points}`}
              accessibilityValue={{ min: 0, max: 100, now: row.percentage }}
              style={styles.category}
              testID={`category-bar-${row.category_id}`}
            >
              <View style={styles.categoryMeta}>
                <Text style={styles.categoryLabel}>{row.label}</Text>
                <Text style={styles.categoryFigure}>
                  {row.score}
                  <Text style={styles.categoryMax}> / {row.max_points}</Text>
                </Text>
              </View>
              <View style={styles.categoryTrack}>
                <View style={[styles.categoryFill, { width: `${row.percentage}%` }]} />
              </View>
            </View>
          ))}
        </View>
        <View style={styles.column}>
          <View testID="report-strongest" style={styles.lead}>
            <Text style={styles.kicker}>Strongest area</Text>
            <Text style={styles.leadTitle}>{summary.strongest_area.label}</Text>
            <Text style={styles.quiet}>
              {summary.strongest_area.score} / {summary.strongest_area.max_points}
            </Text>
            {strongestQuote ? <Text style={styles.pull}>{strongestQuote}</Text> : null}
          </View>
          <View testID="report-priority-gap" style={styles.lead}>
            <Text style={styles.kicker}>Priority gap</Text>
            <Text style={styles.leadTitle}>
              {summary.priority_gap ? summary.priority_gap.criterion_label : 'No priority gap on this report.'}
            </Text>
            {summary.priority_gap ? (
              <Text style={styles.quiet}>
                {summary.priority_gap.awarded_points} / {summary.priority_gap.max_points} ·{' '}
                {summary.priority_gap.current_anchor_label}
              </Text>
            ) : null}
            {gapQuote ? <Text style={styles.pull}>{gapQuote}</Text> : null}
          </View>
        </View>
      </View>

      <View testID="report-strengths" style={styles.section}>
        <Text style={styles.sectionTitle}>Strengths</Text>
        {report.strengths.length === 0 ? (
          <Text style={styles.quiet}>No strengths listed.</Text>
        ) : (
          report.strengths.map((row) => {
            const open = overlapIds.has(row.criterion_id) ? openPointsOnStrength(row, report.material_gaps) : null;
            return (
              <View key={row.criterion_id} style={styles.row}>
                <Text style={styles.line}>
                  {row.criterion_label} — {row.anchor_label}
                  {open != null ? ` · ${open} points still open` : ''}
                </Text>
                {row.evidence_note ? <Text style={styles.quiet}>{row.evidence_note}</Text> : null}
              </View>
            );
          })
        )}
      </View>

      <View testID="report-material-gaps" style={styles.section}>
        <Text style={styles.sectionTitle}>Areas to strengthen</Text>
        {remainingGaps.length === 0 ? (
          <Text style={styles.quiet}>No areas to strengthen listed.</Text>
        ) : (
          remainingGaps.map((row) => (
            <Text key={row.criterion_id} style={styles.line}>
              {row.criterion_label} — {row.current_anchor_label}
            </Text>
          ))
        )}
      </View>

      <View testID="report-priority-actions" style={styles.section}>
        <Text style={styles.sectionTitle}>Five priority actions</Text>
        <Text style={styles.quiet}>these actions target {summary.open_points} open points.</Text>
        {report.priority_actions.map((row) => (
          <View
            key={row.action_id}
            {...webClass('ss-editorial-step')}
            style={styles.step}
            testID={`priority-action-${row.priority_order}`}
          >
            <Text {...webClass('ss-step-index')} style={styles.stepIndex}>
              {String(row.priority_order).padStart(2, '0')}
            </Text>
            <View style={styles.stepCopy}>
              <Text style={styles.stepTitle}>{row.candidate_instruction}</Text>
              <Text style={styles.body}>{row.evidence_lead}</Text>
              <Text style={styles.line}>Required output: {row.required_output}</Text>
              <Text style={styles.quiet}>Completion check: {row.completion_check}</Text>
            </View>
          </View>
        ))}
      </View>

      <View testID="report-project-recommendation" style={styles.section}>
        <ProjectBrief report={report} />
      </View>

      <View {...webClass('ss-edition-screen-criteria')} testID="report-criterion-breakdown" style={styles.section}>
        <Text style={styles.sectionTitle}>Detailed criterion breakdown</Text>
        {groups.map((group) => (
          <Accordion
            key={group.category_id}
            title={group.category_label}
            defaultExpanded={false}
            testID={`criterion-group-${group.category_id}`}
          >
            {group.items.map((row) => (
              <View key={row.criterion_id} style={styles.criterion}>
                <Text style={styles.line}>
                  {row.criterion_label} · {row.anchor_label} · {row.awarded_points}/{row.max_points}
                </Text>
                {row.evidence_note ? (
                  <Text style={styles.quiet} testID={`criterion-note-${row.criterion_id}`}>
                    {row.evidence_note}
                  </Text>
                ) : null}
              </View>
            ))}
          </Accordion>
        ))}
      </View>

      {Platform.OS === 'web' ? (
        <View {...webClass('ss-edition-print-criteria')} testID="report-print-criteria">
          <Text style={styles.sectionTitle}>Criterion record</Text>
          {report.criterion_breakdown.map((row) => (
            <Text key={row.criterion_id} style={styles.line}>
              {row.criterion_label} · {row.anchor_label} · {row.awarded_points}/{row.max_points}. {row.evidence_note}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function ProjectBrief({ report }: { report: ReadinessReport }) {
  const project = report.project_recommendation;

  if (project == null) {
    return <Text style={styles.quiet}>No project recommendation available.</Text>;
  }
  if (project.status === 'REVIEW_REQUIRED') {
    return (
      <Text style={styles.body}>
        A project recommendation is not available until this assessment has been reviewed.
      </Text>
    );
  }

  return (
    <View {...webClass('ss-edition-brief')} style={styles.brief}>
      <Text style={styles.kicker}>Build brief</Text>
      <Text style={styles.leadTitle}>{project.title}</Text>
      <Text style={styles.deck}>{project.scenario}</Text>
      {project.required_foundations.length > 0 ? (
        <Text style={styles.line}>Prerequisites: {project.required_foundations.join('; ')}.</Text>
      ) : null}
      {project.required_outputs.map((item, index) => (
        <Text key={item} style={styles.line}>
          {index + 1}. {item}
        </Text>
      ))}
      {project.completion_checks.length > 0 ? (
        <Text style={styles.body}>{project.completion_checks.join(' ')}</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  stack: {
    gap: 28,
    minWidth: 0,
    backgroundColor: Palette.paper,
  },
  track: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 1.1,
    textTransform: 'uppercase',
  },
  columns: {
    gap: 28,
    minWidth: 0,
  },
  columnsWide: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  column: {
    flexGrow: 1,
    flexBasis: 280,
    gap: 16,
    minWidth: 0,
  },
  kicker: {
    color: Palette.green,
    fontFamily: FontFamily.sans,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  category: {
    gap: 8,
    minWidth: 0,
  },
  categoryMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    gap: 12,
  },
  categoryLabel: {
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 15,
    lineHeight: 22,
    flexShrink: 1,
  },
  categoryFigure: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 28,
    lineHeight: 32,
  },
  categoryMax: {
    color: Palette.muted,
    fontFamily: FontFamily.serif,
    fontSize: 14,
    lineHeight: 20,
  },
  categoryTrack: {
    height: 2,
    backgroundColor: Palette.divider,
  },
  categoryFill: {
    height: 2,
    backgroundColor: Palette.green,
  },
  lead: {
    gap: 8,
    minWidth: 0,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: Palette.ink,
  },
  leadTitle: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 28,
    lineHeight: 32,
  },
  pull: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 18,
    lineHeight: 26,
    borderLeftWidth: 3,
    borderLeftColor: Palette.green,
    paddingLeft: 12,
  },
  section: {
    gap: 12,
    minWidth: 0,
  },
  sectionTitle: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 28,
    lineHeight: 32,
  },
  row: {
    gap: 4,
    minWidth: 0,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: Palette.divider,
  },
  step: {
    flexDirection: 'row',
    gap: 12,
    minWidth: 0,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: Palette.divider,
  },
  stepIndex: {
    width: 48,
    color: '#b8bbb7',
    fontFamily: FontFamily.serif,
    fontSize: 32,
    lineHeight: 36,
  },
  stepCopy: {
    flex: 1,
    gap: 6,
    minWidth: 0,
  },
  stepTitle: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 22,
    lineHeight: 26,
  },
  deck: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 20,
    lineHeight: 28,
  },
  brief: {
    gap: 10,
    minWidth: 0,
    padding: 20,
    borderWidth: 1,
    borderColor: Palette.ink,
    backgroundColor: Palette.surface,
  },
  body: {
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 16,
    lineHeight: 24,
  },
  line: {
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 15,
    lineHeight: 22,
  },
  quiet: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 15,
    lineHeight: 22,
  },
  criterion: {
    gap: 4,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: Palette.divider,
    minWidth: 0,
  },
});
