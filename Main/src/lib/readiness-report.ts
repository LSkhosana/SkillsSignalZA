import type { CriterionBreakdownRow, MaterialGapRow, StrengthRow } from '@/services/api';

export type CriterionCategoryGroup = {
  category_id: string;
  category_label: string;
  items: CriterionBreakdownRow[];
};

export function groupCriteriaByCategory(rows: CriterionBreakdownRow[]): CriterionCategoryGroup[] {
  const groups: CriterionCategoryGroup[] = [];
  const index = new Map<string, CriterionCategoryGroup>();

  for (const row of rows) {
    let group = index.get(row.category_id);
    if (!group) {
      group = {
        category_id: row.category_id,
        category_label: row.category_label,
        items: [],
      };
      index.set(row.category_id, group);
      groups.push(group);
    }
    group.items.push(row);
  }

  return groups;
}

export function overlappingStrengthIds(strengths: StrengthRow[], gaps: MaterialGapRow[]): Set<string> {
  const gapIds = new Set(gaps.map((row) => row.criterion_id));
  return new Set(strengths.filter((row) => gapIds.has(row.criterion_id)).map((row) => row.criterion_id));
}

export function gapsOutsideStrengths(strengths: StrengthRow[], gaps: MaterialGapRow[]): MaterialGapRow[] {
  const overlap = overlappingStrengthIds(strengths, gaps);
  return gaps.filter((row) => !overlap.has(row.criterion_id));
}

export function openPointsOnStrength(strength: StrengthRow, gaps: MaterialGapRow[]): number | null {
  const gap = gaps.find((row) => row.criterion_id === strength.criterion_id);
  return gap ? gap.point_gap : null;
}

export function evidenceNoteForCriterion(rows: CriterionBreakdownRow[], criterionId: string): string | null {
  const note = rows.find((row) => row.criterion_id === criterionId)?.evidence_note.trim();
  return note ? note : null;
}

export function evidenceNoteForCategory(
  categoryId: string,
  strengths: StrengthRow[],
  rows: CriterionBreakdownRow[],
): string | null {
  const fromStrengths = strengths
    .filter((row) => row.category_id === categoryId && row.evidence_note.trim())
    .sort((left, right) => right.awarded_points - left.awarded_points);
  if (fromStrengths[0]) {
    return fromStrengths[0].evidence_note;
  }
  const fromCriteria = rows
    .filter((row) => row.category_id === categoryId && row.evidence_note.trim())
    .sort((left, right) => right.awarded_points - left.awarded_points);
  return fromCriteria[0]?.evidence_note ?? null;
}
