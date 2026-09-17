'use client';

import React from 'react';
import Link from 'next/link';
import type { InventoryProduct } from '../../lib/inventory';
import { StockStatusBadge } from './StockStatusBadge';

/**
 * Props accepted by the ProductTable component.
 */
export interface ProductTableProps {
  /** List of inventory product records to display in the table. */
  readonly products: readonly InventoryProduct[];
}

/**
 * Maps raw warehouse ID codes to human-readable TrackFlow warehouse location labels.
 *
 * @param warehouseId - Code representing warehouse origin (e.g. 'wh-la', 'wh-zgz').
 * @returns Human-readable warehouse display title.
 */
function getWarehouseLabel(warehouseId: string): string {
  switch (warehouseId.toLowerCase()) {
    case 'wh-la':
      return 'Los Angeles (wh-la)';
    case 'wh-zgz':
      return 'Zaragoza (wh-zgz)';
    default:
      return warehouseId;
  }
}

/**
 * Product table component rendering live product stock inventory with status badges and order action buttons.
 *
 * @param props - Component props containing products array.
 * @returns JSX Element rendering formatted products table or empty state notice.
 */
export function ProductTable(props: ProductTableProps): React.ReactElement {
  const { products } = props;

  if (products.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center shadow-lg">
        <p className="text-base text-slate-400">No inventory products registered in the system.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/80 shadow-xl backdrop-blur-sm">
      <table className="w-full text-left text-sm text-slate-300">
        <thead className="border-b border-slate-800 bg-slate-950/60 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <tr>
            <th scope="col" className="px-6 py-4">SKU Code</th>
            <th scope="col" className="px-6 py-4">Product Name</th>
            <th scope="col" className="px-6 py-4">Warehouse Location</th>
            <th scope="col" className="px-6 py-4 text-center">Current Stock</th>
            <th scope="col" className="px-6 py-4 text-center">Stock Status</th>
            <th scope="col" className="px-6 py-4 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60 font-medium">
          {products.map((product) => (
            <tr key={product.id} className="hover:bg-slate-800/40 transition-colors">
              <td className="px-6 py-4 whitespace-nowrap font-mono font-bold text-emerald-400">
                {product.sku}
              </td>
              <td className="px-6 py-4 text-slate-100 font-semibold">
                {product.name}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-slate-400 text-xs">
                {getWarehouseLabel(product.warehouse_id)}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-center font-mono font-bold text-slate-100 text-base">
                {product.current_stock}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-center">
                <StockStatusBadge
                  currentStock={product.current_stock}
                  lowStockThreshold={product.low_stock_threshold}
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right">
                <div className="inline-flex items-center justify-end gap-2">
                  <Link
                    href={`/inventory/orders/inbound?sku_id=${product.id}`}
                    className="inline-flex items-center gap-1 rounded-md bg-emerald-950/80 px-3 py-1.5 text-xs font-semibold text-emerald-300 border border-emerald-700/60 hover:bg-emerald-900 hover:text-white transition-all shadow-sm"
                  >
                    <span>+</span> Inbound
                  </Link>
                  <Link
                    href={`/inventory/orders/outbound?sku_id=${product.id}`}
                    className="inline-flex items-center gap-1 rounded-md bg-sky-950/80 px-3 py-1.5 text-xs font-semibold text-sky-300 border border-sky-700/60 hover:bg-sky-900 hover:text-white transition-all shadow-sm"
                  >
                    <span>-</span> Outbound
                  </Link>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default ProductTable;
