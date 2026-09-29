'use client';

import React, { useMemo } from 'react';
import type { InventoryOrderRecord } from '../../lib/inventory';

/**
 * Composite summary metrics computed across the historical order ledger.
 */
export interface OrdersLedgerSummary {
  /** Sum of all inbound inventory quantities received. */
  readonly totalInboundUnits: number;
  /** Sum of all outbound inventory quantities dispatched. */
  readonly totalOutboundUnits: number;
  /** Net movement delta (totalInboundUnits - totalOutboundUnits). */
  readonly netMovement: number;
  /** Total count of inbound deliveries. */
  readonly inboundCount: number;
  /** Total count of outbound exits. */
  readonly outboundCount: number;
}

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
 * Orders history ledger table component with memoized volume and transaction aggregates.
 *
 * Displays a read-only list of historical stock entries and exits with distinct badges for
 * inbound vs outbound movements, product SKU codes, movement quantities, creation dates, and user_uuid.
 *
 * @param props - Component props containing orders array.
 * @returns JSX Element rendering the audit-ready orders ledger table with memoized KPI cards.
 */
export function OrdersHistoryTable(props: OrdersHistoryTableProps): React.ReactElement {
  const { orders } = props;

  // Non-trivial calculation iterating through orders to compute multi-metric aggregates
  const summary = useMemo<OrdersLedgerSummary>(() => {
    let inboundUnits = 0;
    let outboundUnits = 0;
    let inboundTally = 0;
    let outboundTally = 0;

    for (const order of orders) {
      if (order.order_type === 'inbound') {
        inboundUnits += order.quantity;
        inboundTally += 1;
      } else {
        outboundUnits += order.quantity;
        outboundTally += 1;
      }
    }

    return {
      totalInboundUnits: inboundUnits,
      totalOutboundUnits: outboundUnits,
      netMovement: inboundUnits - outboundUnits,
      inboundCount: inboundTally,
      outboundCount: outboundTally,
    };
  }, [orders]);

  if (orders.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center shadow-lg">
        <p className="text-base text-slate-400">No inventory order records found in the ledger.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Memoized KPI Summary Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-4">
          <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Total Inbound Units</p>
          <p className="text-2xl font-bold text-emerald-400 mt-1">+{summary.totalInboundUnits.toLocaleString()}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">{summary.inboundCount} shipments received</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-4">
          <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Total Outbound Units</p>
          <p className="text-2xl font-bold text-sky-400 mt-1">-{summary.totalOutboundUnits.toLocaleString()}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">{summary.outboundCount} stock exits logged</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-4">
          <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Net Movement Delta</p>
          <p className={`text-2xl font-bold mt-1 ${summary.netMovement >= 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
            {summary.netMovement >= 0 ? `+${summary.netMovement.toLocaleString()}` : summary.netMovement.toLocaleString()}
          </p>
          <p className="text-[11px] text-slate-400 mt-0.5">warehouse net delta</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-4">
          <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Total Transactions</p>
          <p className="text-2xl font-bold text-slate-100 mt-1">{orders.length}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">audit ledger entries</p>
        </div>
      </div>

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
    </div>
  );
}

export default OrdersHistoryTable;
