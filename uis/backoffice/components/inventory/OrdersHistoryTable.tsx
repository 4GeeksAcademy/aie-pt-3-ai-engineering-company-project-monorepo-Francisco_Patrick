'use client';

import React from 'react';
import type { InventoryOrderRecord } from '../../lib/inventory';

/**
 * Props accepted by the OrdersHistoryTable component.
 */
export interface OrdersHistoryTableProps {
  /** Array of historical inventory order records to render. */
  readonly orders: readonly InventoryOrderRecord[];
}

/**
 * Formats an ISO date string into a readable timestamp format.
 *
 * @param dateString - ISO format date-time string.
 * @returns Formatted date and time string.
 */
function formatTimestamp(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return dateString;
  }
}

/**
 * Orders history ledger table component.
 *
 * Displays a read-only list of historical stock entries and exits with distinct badges for
 * inbound vs outbound movements, product SKU codes, movement quantities, creation dates, and user_uuid.
 *
 * @param props - Component props containing orders array.
 * @returns JSX Element rendering the audit-ready orders ledger table.
 */
export function OrdersHistoryTable(props: OrdersHistoryTableProps): React.ReactElement {
  const { orders } = props;

  if (orders.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center shadow-lg">
        <p className="text-base text-slate-400">No inventory order records found in the ledger.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/80 shadow-xl backdrop-blur-sm">
      <table className="w-full text-left text-sm text-slate-300">
        <thead className="border-b border-slate-800 bg-slate-950/60 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <tr>
            <th scope="col" className="px-6 py-4">Order ID</th>
            <th scope="col" className="px-6 py-4">Order Type</th>
            <th scope="col" className="px-6 py-4">Product Code (SKU)</th>
            <th scope="col" className="px-6 py-4">Warehouse</th>
            <th scope="col" className="px-6 py-4 text-center">Quantity</th>
            <th scope="col" className="px-6 py-4">Logged By (User UUID)</th>
            <th scope="col" className="px-6 py-4 text-right">Timestamp</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60 font-medium">
          {orders.map((order) => {
            const isInbound = order.order_type === 'inbound';
            return (
              <tr key={order.id} className="hover:bg-slate-800/40 transition-colors">
                <td className="px-6 py-4 whitespace-nowrap font-mono text-xs text-slate-400">
                  #{order.id}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {isInbound ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-800/60 shadow-sm">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                      📥 INBOUND (Delivery)
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-950/80 text-sky-300 border border-sky-800/60 shadow-sm">
                      <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
                      📤 OUTBOUND (Exit)
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap font-mono font-bold text-white">
                  {order.sku_code}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-xs text-slate-400 font-mono">
                  {order.warehouse_id}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-center font-mono font-bold text-slate-100 text-base">
                  {isInbound ? `+${order.quantity}` : `-${order.quantity}`}
                </td>
                <td className="px-6 py-4 whitespace-nowrap font-mono text-xs text-emerald-400">
                  {order.user_uuid}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-xs text-slate-400">
                  {formatTimestamp(order.created_at)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default OrdersHistoryTable;
