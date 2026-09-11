import { useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '@/hooks/use-theme';
import type { ReadinessReport } from '@/services/api';
import { Spacing } from '@/theme';

type ReadinessReportViewProps = {
  report: ReadinessReport;
};

export function ReadinessReportView({ report }: ReadinessReportViewProps) {
  const theme = useTheme();
  const summary = report.score_summary;

  return (
    <View style={styles.stack} testID="full-report">
      <Section title="Score and band" testID="report-score-band">
        <Text style={[styles.score, { color: theme.text }]}>
          {summary.final_score} / {summary.score_max}
        </Text>
        <Text style={[styles.body, { color: theme.text }]}>{summary.band_label}</Text>
        <Text style={[styles.meta, { color: theme.textSecondary }]}>{report.track_label}</Text>
      </Section>

      <Section title="Benchmark and disclaimer" testID="report-benchmark">
        <Text style={[styles.body, { color: theme.text }]}>{report.benchmark.scope_statement}</Text>
        <Text style={[styles.meta, { color: theme.textSecondary }]}>{report.benchmark.disclaimer}</Text>
      </Section>

      <Section title="Strongest area" testID="report-strongest">
        <Text style={[styles.body, { color: theme.text }]}>{summary.strongest_area.label}</Text>
        <Text style={[styles.meta, { color: theme.textSecondary }]}>
          {summary.strongest_area.score} / {summary.strongest_area.max_points} ({summary.strongest_area.percentage}
          %)
        </Text>
      </Section>

      <Section title="Priority gap" testID="report-priority-gap">
        <Text style={[styles.body, { color: theme.text }]}>
          {summary.priority_gap ? summary.priority_gap.criterion_label : 'No priority gap on this report.'}
        </Text>
      </Section>

      <Section title="Category breakdown" testID="report-category-breakdown">
        {report.category_breakdown.map((row) => (
          <Text key={row.category_id} style={[styles.meta, { color: theme.text }]}>
            {row.label}: {row.score} / {row.max_points} ({row.percentage}%)
          </Text>
        ))}
      </Section>

      <Section title="Strengths" testID="report-strengths">
        {report.strengths.length === 0 ? (
          <Text style={[styles.meta, { color: theme.textSecondary }]}>No strengths listed.</Text>
        ) : (
          report.strengths.map((row) => (
            <Text key={row.criterion_id} style={[styles.meta, { color: theme.text }]}>
              {row.criterion_label} — {row.anchor_label}
            </Text>
          ))
        )}
      </Section>

      <Section title="Material gaps" testID="report-material-gaps">
        {report.material_gaps.length === 0 ? (
          <Text style={[styles.meta, { color: theme.textSecondary }]}>No material gaps listed.</Text>
        ) : (
          report.material_gaps.map((row) => (
            <Text key={row.criterion_id} style={[styles.meta, { color: theme.text }]}>
              {row.criterion_label} — {row.current_anchor_label}
            </Text>
          ))
        )}
      </Section>

      <Section title="Priority actions" testID="report-priority-actions">
        {report.priority_actions.map((row) => (
          <View key={row.action_id} style={styles.action}>
            <Text style={[styles.body, { color: theme.text }]}>
              {row.priority_order}. {row.candidate_instruction}
            </Text>
            <Text style={[styles.meta, { color: theme.textSecondary }]}>Required output: {row.required_output}</Text>
            <Text style={[styles.meta, { color: theme.textSecondary }]}>
              Completion check: {row.completion_check}
            </Text>
          </View>
        ))}
      </Section>

      <Section title="Project recommendation" testID="report-project-recommendation">
        <ProjectBlock report={report} />
      </Section>

      <Section title="Criterion breakdown" testID="report-criterion-breakdown">
        {report.criterion_breakdown.map((row) => (
          <CriterionRow
            key={row.criterion_id}
            label={row.criterion_label}
            detail={`${row.category_label} · ${row.anchor_label} · ${row.awarded_points}/${row.max_points}${row.evidence_note ? ` · ${row.evidence_note}` : ''}`}
          />
        ))}
      </Section>
    </View>
  );
}

function ProjectBlock({ report }: { report: ReadinessReport }) {
  const theme = useTheme();
  const project = report.project_recommendation;

  if (project == null) {
    return <Text style={[styles.meta, { color: theme.textSecondary }]}>No project recommendation available.</Text>;
  }
  if (project.status === 'REVIEW_REQUIRED') {
    return (
      <Text style={[styles.body, { color: theme.text }]}>
        A project recommendation is not available until this assessment has been reviewed.
      </Text>
    );
  }

  return (
    <View style={styles.action}>
      <Text style={[styles.body, { color: theme.text }]}>{project.title}</Text>
      <Text style={[styles.meta, { color: theme.textSecondary }]}>{project.scenario}</Text>
      {project.required_foundations.map((item) => (
        <Text key={item} style={[styles.meta, { color: theme.text }]}>
          Foundation: {item}
        </Text>
      ))}
      {project.required_outputs.map((item) => (
        <Text key={item} style={[styles.meta, { color: theme.text }]}>
          Output: {item}
        </Text>
      ))}
      {project.completion_checks.map((item) => (
        <Text key={item} style={[styles.meta, { color: theme.text }]}>
          Check: {item}
        </Text>
      ))}
    </View>
  );
}

function CriterionRow({ label, detail }: { label: string; detail: string }) {
  const theme = useTheme();
  const [open, setOpen] = useState(false);

  return (
    <View style={[styles.criterion, { borderColor: theme.border }]}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={`${open ? 'Collapse' : 'Expand'} ${label}`}
        onPress={() => setOpen((value) => !value)}
        style={styles.criterionHeader}
      >
        <Text style={[styles.body, { color: theme.text, flex: 1 }]}>{label}</Text>
        <Text style={[styles.meta, { color: theme.accent }]}>{open ? 'Hide' : 'Show'}</Text>
      </Pressable>
      {open ? <Text style={[styles.meta, { color: theme.textSecondary }]}>{detail}</Text> : null}
    </View>
  );
}

function Section({
  title,
  children,
  testID,
}: {
  title: string;
  children: ReactNode;
  testID: string;
}) {
  const theme = useTheme();
  return (
    <View style={styles.section} testID={testID}>
      <Text style={[styles.sectionTitle, { color: theme.text }]}>{title}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  stack: {
    gap: Spacing.lg,
  },
  section: {
    gap: Spacing.sm,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  score: {
    fontSize: 32,
    fontWeight: '700',
  },
  body: {
    fontSize: 16,
    lineHeight: 24,
  },
  meta: {
    fontSize: 15,
    lineHeight: 22,
  },
  action: {
    gap: 4,
  },
  criterion: {
    borderWidth: 1,
    borderRadius: 10,
    padding: Spacing.sm,
    gap: Spacing.sm,
  },
  criterionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    minHeight: 44,
  },
});
