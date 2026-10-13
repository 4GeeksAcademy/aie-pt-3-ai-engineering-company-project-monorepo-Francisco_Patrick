'use client';

import React, { useState, useEffect, useCallback, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams, useRouter } from 'next/navigation';
import type { InventoryProduct, InboundOrderPayload } from '../../../../lib/inventory';
import { getInventoryProducts, createInboundOrder } from '../../../../lib/inventory';
import { InboundOrderForm } from '../../../../components/inventory/InboundOrderForm';

/**
 * Internal component content reading URL search parameters.
 */
function InboundOrderContent(): React.ReactElement {
  const searchParams = useSearchParams();
  const router = useRouter();
  const rawSkuId = searchParams ? searchParams.get('sku_id') : null;
  const initialSkuId = rawSkuId ? parseInt(rawSkuId, 10) : undefined;

  const [products, setProducts] = useState<readonly InventoryProduct[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchProductsList = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      const data = await getInventoryProducts();
      setProducts(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load products list.';
      setApiError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProductsList();
  }, [fetchProductsList]);

  const handleSubmitInboundOrder = async (payload: InboundOrderPayload): Promise<void> => {
    setIsSubmitting(true);
    setApiError(null);
    setSuccessMessage(null);

    try {
      const result = await createInboundOrder(payload);
      setSuccessMessage(
        `Inbound order #${result.id} successfully registered! Received ${result.quantity} unit(s) of ${result.sku_code}.`
      );
      // Refresh products list so updated current_stock is reflected
      await fetchProductsList();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred while creating the inbound order.';
      setApiError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Action Header Links */}
      <div className="flex items-center justify-between">
        <Link
          href="/inventory/products"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
        >
          <span>←</span> Back to Inventory Products
        </Link>
        <Link
          href="/inventory/orders"
          className="inline-flex items-center gap-2 text-xs font-semibold text-emerald-400 hover:text-emerald-300 transition-colors"
        >
          View Orders History Ledger <span>→</span>
        </Link>
      </div>

      {/* Success Confirmation Banner */}
      {successMessage && (
        <div className="rounded-xl bg-emerald-950/80 p-5 text-sm text-emerald-200 border border-emerald-800/80 flex items-center justify-between gap-4 shadow-xl">
          <div className="flex items-center gap-3">
            <span className="text-xl">✅</span>
            <span>{successMessage}</span>
          </div>
          <button
            onClick={() => { router.push('/inventory/orders'); }}
            className="px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-800 hover:bg-emerald-700 text-white transition-all shrink-0"
          >
            View Orders Ledger
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center p-16 space-y-4 rounded-xl border border-slate-800 bg-slate-900/40">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-emerald-500 border-t-transparent" />
          <p className="text-sm font-medium text-slate-400">Loading products for inbound order...</p>
        </div>
      ) : (
        <InboundOrderForm
          products={products}
          initialSkuId={initialSkuId}
          onSubmit={handleSubmitInboundOrder}
          isSubmitting={isSubmitting}
          apiError={apiError}
        />
      )}
    </div>
  );
}

/**
 * Inbound Order Page Component wrapped in Suspense for Next.js searchParams hydration.
 *
 * @returns JSX Element rendering the Inbound Order form page.
 */
export default function InboundOrderPage(): React.ReactElement {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-4 sm:p-8">
      <div className="max-w-3xl mx-auto space-y-8">
        <Suspense
          fallback={
            <div className="flex justify-center p-12 text-slate-400">
              Initializing form...
            </div>
          }
        >
          <InboundOrderContent />
        </Suspense>
      </div>
    </main>
  );
}
