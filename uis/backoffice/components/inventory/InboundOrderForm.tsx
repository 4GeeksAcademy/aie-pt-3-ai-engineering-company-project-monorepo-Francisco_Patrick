'use client';

import React, { useState, useEffect, useId } from 'react';
import type { InventoryProduct, InboundOrderPayload } from '../../lib/inventory';

/**
 * Props accepted by the InboundOrderForm component.
 */
export interface InboundOrderFormProps {
  /** Array of available inventory products to populate the dropdown. */
  readonly products: readonly InventoryProduct[];
  /** Optional initial selected product ID (e.g. from URL query string). */
  readonly initialSkuId?: number | undefined;
  /** Async callback function invoked when the form is submitted. */
  readonly onSubmit: (payload: InboundOrderPayload) => Promise<void>;
  /** Indicates whether form submission is currently in progress. */
  readonly isSubmitting: boolean;
  /** Server-returned error message to display in a visible error element. */
  readonly apiError: string | null;
}

/**
 * Inbound supplier delivery order form component.
 *
 * Features:
 * - Product selector listing all available products by human-readable name and SKU.
 * - Automatic clearing of form inputs upon successful submission.
 * - Visible error message alert rendering on 400/500 API responses.
 *
 * @param props - Form configuration props including products list and submit handler.
 * @returns JSX Element rendering the inbound order form.
 */
export function InboundOrderForm(props: InboundOrderFormProps): React.ReactElement {
  const { products, initialSkuId, onSubmit, isSubmitting, apiError } = props;

  const productSelectId = useId();
  const quantityInputId = useId();

  const [selectedSkuId, setSelectedSkuId] = useState<number | ''>(
    initialSkuId ?? (products[0] ? products[0].id : '')
  );
  const [quantity, setQuantity] = useState<string>('1');

  // Sync initialSkuId if products load asynchronously
  useEffect(() => {
    if (initialSkuId !== undefined && products.some((p) => p.id === initialSkuId)) {
      setSelectedSkuId(initialSkuId);
    } else if (selectedSkuId === '' && products.length > 0 && products[0]) {
      setSelectedSkuId(products[0].id);
    }
  }, [initialSkuId, products, selectedSkuId]);

  const selectedProduct = products.find((p) => p.id === Number(selectedSkuId));

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();

    if (!selectedProduct) {
      return;
    }

    const parsedQuantity = parseInt(quantity, 10);
    if (isNaN(parsedQuantity) || parsedQuantity <= 0) {
      return;
    }

    await onSubmit({
      sku_id: selectedProduct.id,
      warehouse_id: selectedProduct.warehouse_id,
      quantity: parsedQuantity,
    });

    // Reset quantity field on successful submission trigger
    setQuantity('1');
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 rounded-xl border border-slate-800 bg-slate-900/90 p-6 sm:p-8 shadow-2xl backdrop-blur-md">
      <div>
        <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
          <span>📥</span> Register Inbound Delivery Order
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Record incoming supplier deliveries to increase derived product inventory stock.
        </p>
      </div>

      {/* Product Selector Dropdown */}
      <div className="space-y-2">
        <label htmlFor={productSelectId} className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
          Select Product (SKU & Name)
        </label>
        <select
          id={productSelectId}
          value={selectedSkuId}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
            const val = e.target.value;
            setSelectedSkuId(val ? Number(val) : '');
          }}
          disabled={isSubmitting || products.length === 0}
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:opacity-50 transition-all font-medium"
        >
          {products.length === 0 ? (
            <option value="">No products available</option>
          ) : (
            products.map((product) => (
              <option key={product.id} value={product.id}>
                {product.name} ({product.sku}) — {product.warehouse_id} (Current Stock: {product.current_stock})
              </option>
            ))
          )}
        </select>
      </div>

      {/* Selected Product Information */}
      {selectedProduct && (
        <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-4 flex justify-between items-center">
          <div>
            <span className="text-xs text-slate-400 font-medium">Destination Warehouse:</span>
            <p className="text-sm font-bold text-emerald-400 font-mono">{selectedProduct.warehouse_id}</p>
          </div>
          <div className="text-right">
            <span className="text-xs text-slate-400 font-medium">Current Stock Count:</span>
            <p className="text-sm font-bold text-white font-mono">{selectedProduct.current_stock} units</p>
          </div>
        </div>
      )}

      {/* Quantity Input Field */}
      <div className="space-y-2">
        <label htmlFor={quantityInputId} className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
          Inbound Delivery Quantity
        </label>
        <input
          id={quantityInputId}
          type="number"
          min="1"
          step="1"
          value={quantity}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQuantity(e.target.value)}
          disabled={isSubmitting || !selectedProduct}
          placeholder="e.g. 50"
          required
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm font-mono text-white outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:opacity-50 transition-all"
        />
      </div>

      {/* Visible Server API Error Display */}
      {apiError && (
        <div className="rounded-lg bg-red-950/90 p-4 text-xs text-red-200 border border-red-800 flex items-center gap-3 shadow-md">
          <span className="text-base">🚨</span>
          <div>
            <span className="font-bold">API Submission Error:</span> {apiError}
          </div>
        </div>
      )}

      {/* Submit Button */}
      <div className="pt-2">
        <button
          type="submit"
          disabled={isSubmitting || !selectedProduct || parseInt(quantity, 10) <= 0}
          className="w-full rounded-lg bg-emerald-600 hover:bg-emerald-500 py-3.5 px-6 text-sm font-bold text-white shadow-lg shadow-emerald-950/50 transition-all disabled:opacity-50 shrink-0"
        >
          {isSubmitting ? 'Processing Inbound Delivery...' : 'Confirm Inbound Delivery'}
        </button>
      </div>
    </form>
  );
}

export default InboundOrderForm;
