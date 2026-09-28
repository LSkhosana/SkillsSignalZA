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
