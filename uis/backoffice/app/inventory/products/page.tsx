'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import type { InventoryProduct } from '../../../lib/inventory';
import { getInventoryProducts } from '../../../lib/inventory';
import { ProductTable } from '../../../components/inventory/ProductTable';

/**
 * Backoffice Inventory Products Listing Page Component.
 *
 * @returns JSX Element rendering live inventory stock list with visual badges and action triggers.
 */
export default function InventoryProductsPage(): React.ReactElement {
  const [products, setProducts] = useState<readonly InventoryProduct[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProductsList = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const data = await getInventoryProducts();
      setProducts(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An unexpected error occurred while loading inventory products.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProductsList();
  }, [fetchProductsList]);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-4 sm:p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/80 pb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
              <span>📦</span> TrackFlow Inventory Products
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Real-time stock level monitoring across Los Angeles (<code className="text-emerald-400 font-mono">wh-la</code>) and Zaragoza (<code className="text-emerald-400 font-mono">wh-zgz</code>) warehouses.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <Link
              href="/inventory/orders/inbound"
              className="inline-flex items-center gap-2 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-500 px-4 py-2.5 rounded-lg transition-all shadow-lg shadow-emerald-950/40"
            >
              <span>+</span> Register Inbound Delivery
            </Link>
            <Link
              href="/inventory/orders/outbound"
              className="inline-flex items-center gap-2 text-sm font-semibold text-white bg-sky-600 hover:bg-sky-500 px-4 py-2.5 rounded-lg transition-all shadow-lg shadow-sky-950/40"
            >
              <span>-</span> Log Outbound Exit
            </Link>
            <Link
              href="/inventory/orders"
              className="inline-flex items-center gap-2 text-sm font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 hover:text-white px-4 py-2.5 rounded-lg transition-all border border-slate-700"
            >
              <span>📋</span> Orders History
            </Link>
          </div>
        </div>

        {/* Error Alert Display */}
        {error && (
          <div className="rounded-xl bg-red-950/80 p-5 text-sm text-red-200 border border-red-800/80 flex items-center justify-between gap-4 shadow-lg">
            <div className="flex items-center gap-3">
              <span className="text-lg">⚠️</span>
              <span>{error}</span>
            </div>
            <button
              onClick={() => { fetchProductsList(); }}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-red-800 hover:bg-red-700 text-white transition-all shrink-0 shadow-sm"
            >
              🔄 Retry Loading
            </button>
          </div>
        )}

        {/* Main Content Area */}
        {loading ? (
          <div className="flex flex-col items-center justify-center p-16 space-y-4 rounded-xl border border-slate-800 bg-slate-900/40">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-emerald-500 border-t-transparent" />
            <p className="text-sm font-medium text-slate-400">Fetching live inventory stock levels...</p>
          </div>
        ) : (
          <ProductTable products={products} />
        )}
      </div>
    </main>
  );
}
