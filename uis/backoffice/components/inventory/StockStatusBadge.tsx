'use client';

import React from 'react';

/**
 * Props accepted by the StockStatusBadge component.
 */
export interface StockStatusBadgeProps {
  /** The current quantity of stock available for a given product. */
  readonly currentStock: number;
  /** The threshold value at or below which stock is considered low. */
  readonly lowStockThreshold: number;
}

/**
 * Visual stock status indicator badge component.
 *
 * Threshold logic:
 * - Out of Stock (Red): currentStock === 0
 * - Low Stock (Amber): 0 < currentStock <= lowStockThreshold
 * - Healthy Stock (Green): currentStock > lowStockThreshold
 *
 * @param props - Stock counts and threshold configuration.
 * @returns JSX Element rendering styled badge with status text and icon.
 */
export function StockStatusBadge(props: StockStatusBadgeProps): React.ReactElement {
  const { currentStock, lowStockThreshold } = props;

  if (currentStock <= 0) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-950/80 text-red-400 border border-red-800/60 shadow-sm">
        <span className="h-1.5 w-1.5 rounded-full bg-red-400 animate-pulse" />
        Out of Stock (0)
      </span>
    );
  }

  if (currentStock <= lowStockThreshold) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-950/80 text-amber-300 border border-amber-800/60 shadow-sm">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
        Low Stock ({currentStock})
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-800/60 shadow-sm">
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
      Healthy Stock ({currentStock})
    </span>
  );
}

export default StockStatusBadge;
