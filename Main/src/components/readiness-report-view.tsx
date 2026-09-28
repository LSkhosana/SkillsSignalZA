import { StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { SectionHeader } from '@/components/system/section-header';
import { Accordion, Badge, Divider, EditorialCard, ProgressBar } from '@/components/system/surfaces';
import { formatCustomerDate } from '@/lib/assessment-summaries';
import { groupCriteriaByCategory, overlappingStrengthIds } from '@/lib/readiness-report';
import type { ReadinessReport } from '@/services/api';
import { FontFamily, Layout, Palette } from '@/theme/tokens';

type ReadinessReportViewProps = {
  report: ReadinessReport;
};

const OVERLAP_COPY =
  'A criterion can show useful evidence and still appear under Areas to strengthen. That overlap is expected: the evidence already present is a strength, while remaining points mean more evidence can still be added.';

export function ReadinessReportView({ report }: ReadinessReportViewProps) {
  const { width } = useWindowDimensions();
  const compact = width < Layout.mobile;
  const summary = report.score_summary;
  const overlapIds = overlappingStrengthIds(report.strengths, report.material_gaps);
  const groups = groupCriteriaByCategory(report.criterion_breakdown);

  return (
    <View style={styles.stack} testID="full-report">
      <View style={styles.masthead} testID="report-score-band">
        <Text style={styles.kicker}>Readiness score</Text>
        <Text style={[styles.score, compact ? styles.scoreCompact : null]}>
          {summary.final_score} / {summary.score_max}
        </Text>
        <Text style={[styles.band, compact ? styles.bandCompact : null]}>{summary.band_label}</Text>
      </View>

      <View testID="report-track-meta" style={styles.metaBlock}>
        <SectionHeader
          eyebrow={report.track_label}
          title="Readiness Report"
          subtitle={`Assessed ${formatCustomerDate(report.assessed_at)}.`}
        />
        <View testID="report-benchmark" style={styles.benchmark}>
          <Text style={styles.body}>{report.benchmark.scope_statement}</Text>
          <Text style={styles.quiet}>{report.benchmark.disclaimer}</Text>
        </View>
      </View>

      <View style={styles.pair}>
        <View style={styles.pairItem}>
          <EditorialCard testID="report-strongest">
            <Text style={styles.kicker}>Strongest area</Text>
            <Text style={styles.cardTitle}>{summary.strongest_area.label}</Text>
            <Text style={styles.quiet}>
              {summary.strongest_area.score} / {summary.strongest_area.max_points} (
              {summary.strongest_area.percentage}%)
            </Text>
          </EditorialCard>
        </View>
        <View style={styles.pairItem}>
          <EditorialCard testID="report-priority-gap">
            <Text style={styles.kicker}>Priority area</Text>
            <Text style={styles.cardTitle}>
              {summary.priority_gap ? summary.priority_gap.criterion_label : 'No priority area on this report.'}
            </Text>
            {summary.priority_gap ? (
              <Text style={styles.quiet}>
                {summary.priority_gap.awarded_points} / {summary.priority_gap.max_points} ·{' '}
                {summary.priority_gap.current_anchor_label}
              </Text>
            ) : null}
          </EditorialCard>
        </View>
      </View>

      <View testID="report-category-breakdown" style={styles.section}>
        <Text style={styles.sectionTitle}>Category performance</Text>
        {report.category_breakdown.map((row) => (
          <ProgressBar
            key={row.category_id}
            label={`${row.label}: ${row.score} / ${row.max_points}`}
            value={row.percentage}
            testID={`category-bar-${row.category_id}`}
          />
        ))}
      </View>

      <View testID="report-strengths" style={styles.section}>
        <Text style={styles.sectionTitle}>Strengths</Text>
        {report.strengths.length === 0 ? (
          <Text style={styles.quiet}>No strengths listed.</Text>
        ) : (
          report.strengths.map((row) => (
            <Text key={row.criterion_id} style={styles.line}>
              {row.criterion_label} — {row.anchor_label}
            </Text>
          ))
        )}
      </View>

      <View testID="report-material-gaps" style={styles.section}>
        <Text style={styles.sectionTitle}>Areas to strengthen</Text>
        <Text style={styles.overlap} testID="report-overlap-note">
          {OVERLAP_COPY}
        </Text>
        {report.material_gaps.length === 0 ? (
          <Text style={styles.quiet}>No areas to strengthen listed.</Text>
        ) : (
          report.material_gaps.map((row) => (
            <Text key={row.criterion_id} style={styles.line}>
              {row.criterion_label} — {row.current_anchor_label}
              {overlapIds.has(row.criterion_id) ? ' · also listed as a strength' : ''}
            </Text>
          ))
        )}
      </View>

      <View testID="report-priority-actions" style={styles.section}>
        <Text style={styles.sectionTitle}>Five priority actions</Text>
        {report.priority_actions.map((row) => (
          <EditorialCard key={row.action_id} testID={`priority-action-${row.priority_order}`}>
            <Badge label={`${row.priority_order}`} tone="green" />
            <Text style={styles.cardTitle}>{row.candidate_instruction}</Text>
            <Text style={styles.line}>Required output: {row.required_output}</Text>
            <Text style={styles.quiet}>Completion check: {row.completion_check}</Text>
          </EditorialCard>
        ))}
      </View>

      <View testID="report-project-recommendation" style={styles.section}>
        <Text style={styles.sectionTitle}>Recommended project</Text>
        <ProjectBrief report={report} />
      </View>

      <View testID="report-criterion-breakdown" style={styles.section}>
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
                {row.evidence_note ? <Text style={styles.quiet}>{row.evidence_note}</Text> : null}
              </View>
            ))}
          </Accordion>
        ))}
      </View>
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
    <EditorialCard>
      <Text style={styles.kicker}>Build brief</Text>
      <Text style={styles.cardTitle}>{project.title}</Text>
      <Text style={styles.body}>{project.scenario}</Text>
      <Divider />
      {project.required_foundations.map((item) => (
        <Text key={item} style={styles.line}>
          Foundation: {item}
        </Text>
      ))}
      {project.required_outputs.map((item) => (
        <Text key={item} style={styles.line}>
          Output: {item}
        </Text>
      ))}
      {project.completion_checks.map((item) => (
        <Text key={item} style={styles.quiet}>
          Check: {item}
        </Text>
      ))}
    </EditorialCard>
  );
}

const styles = StyleSheet.create({
  stack: {
    gap: 28,
    minWidth: 0,
  },
  masthead: {
    minWidth: 0,
    overflow: 'hidden',
    backgroundColor: Palette.ink,
    paddingHorizontal: 22,
    paddingVertical: 28,
    gap: 10,
  },
  kicker: {
    color: Palette.greenSoft,
    fontFamily: FontFamily.sans,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  score: {
    color: Palette.surface,
    fontFamily: FontFamily.serif,
    fontSize: 64,
    lineHeight: 68,
    letterSpacing: -1.2,
    maxWidth: '100%',
    flexShrink: 1,
  },
  scoreCompact: {
    fontSize: 44,
    lineHeight: 48,
  },
  band: {
    color: Palette.surface,
    fontFamily: FontFamily.serif,
    fontSize: 28,
    lineHeight: 32,
    maxWidth: '100%',
    flexShrink: 1,
  },
  bandCompact: {
    fontSize: 22,
    lineHeight: 26,
  },
  metaBlock: {
    gap: 16,
    minWidth: 0,
  },
  benchmark: {
    gap: 8,
    minWidth: 0,
  },
  pair: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 16,
    minWidth: 0,
  },
  pairItem: {
    flexGrow: 1,
    flexBasis: 280,
    minWidth: 0,
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
  cardTitle: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 24,
    lineHeight: 28,
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
  overlap: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 15,
    lineHeight: 22,
    maxWidth: 720,
  },
  criterion: {
    gap: 4,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: Palette.divider,
    minWidth: 0,
  },
});
