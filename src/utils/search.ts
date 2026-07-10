type Comparable = string | number;

export function linearSearchIndex<T>(
  items: T[],
  predicate: (item: T) => boolean,
): number {
  for (let index = 0; index < items.length; index += 1) {
    const currentItem = items[index];
    if (currentItem !== undefined && predicate(currentItem)) {
      return index;
    }
  }
  return -1;
}

export function binarySearchIndexByField<T extends object>(
  sortedItems: T[],
  field: keyof T,
  target: Comparable,
): number {
  let low = 0;
  let high = sortedItems.length - 1;

  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    const currentItem = sortedItems[middle];

    if (currentItem === undefined) {
      return -1;
    }

    const currentValue = currentItem[field] as Comparable;

    if (currentValue === target) {
      return middle;
    }

    if (currentValue < target) {
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }

  return -1;
}