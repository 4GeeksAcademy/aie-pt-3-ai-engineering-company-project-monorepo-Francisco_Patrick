import type { SortCriterion, SortDirection } from "../types/query.js";

type SortableValue = string | number;

function compareValues(
  left: SortableValue,
  right: SortableValue,
  direction: SortDirection,
): number {
  if (left === right) {
    return 0;
  }

  if (direction === "asc") {
    return left < right ? -1 : 1;
  }

  return left > right ? -1 : 1;
}

export function sortByField<T extends object>(
  items: T[],
  field: keyof T,
  direction: SortDirection,
): T[] {
  return [...items].sort((left: T, right: T) => {
    const leftValue = left[field] as SortableValue;
    const rightValue = right[field] as SortableValue;
    return compareValues(leftValue, rightValue, direction);
  });
}

export function sortByMultipleFields<T extends object>(
  items: T[],
  criteria: SortCriterion<T>[],
): T[] {
  if (criteria.length === 0) {
    return [...items];
  }

  return [...items].sort((left: T, right: T) => {
    for (const criterion of criteria) {
      const leftValue = left[criterion.field] as SortableValue;
      const rightValue = right[criterion.field] as SortableValue;
      const result = compareValues(leftValue, rightValue, criterion.direction);
      if (result !== 0) {
        return result;
      }
    }
    return 0;
  });
}