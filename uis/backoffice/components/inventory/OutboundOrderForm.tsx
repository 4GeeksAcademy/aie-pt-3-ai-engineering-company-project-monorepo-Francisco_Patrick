'use client';

import React, { useState, useEffect, useId } from 'react';
import type { InventoryProduct, OutboundOrderPayload } from '../../lib/inventory';
import { StockStatusBadge } from './StockStatusBadge';

/**
 * Props accepted by the OutboundOrderForm component.
 */
export interface OutboundOrderFormProps {
  /** Array of available inventory products to populate the dropdown. */
  readonly products: readonly InventoryProduct[];
  /** Optional initial selected product ID (e.g. from URL query string). */
  readonly initialSkuId?: number | undefined;
  /** Async callback function invoked when the form is submitted. */
  readonly onSubmit: (payload: OutboundOrderPayload) => Promise<void>;
  /** Indicates whether form submission is currently in progress. */
  readonly isSubmitting: boolean;
  /** Server-returned error message to display inline near quantity input. */
  readonly apiError: string | null;
}

/**
 * Outbound stock exit order form component.
 *
 * Features:
 * - Product selector displaying human-readable name, SKU code, and warehouse location.
 * - Reactive available stock indicator displayed immediately upon product selection.
 * - Client-side warning alert when entered quantity exceeds available stock.
 * - Inline API error message rendering near the quantity input field.
 *
 * @param props - Form configuration props including products list and submit handler.
 * @returns JSX Element rendering the outbound order form.
 */
export function OutboundOrderForm(props: OutboundOrderFormProps): React.ReactElement {
  const { products, initialSkuId, onSubmit, isSubmitting, apiError } = props;

  const productSelectId = useId();
  const quantityInputId = useId();

  const [selectedSkuId, setSelectedSkuId] = useState<number | ''>(
    initialSkuId ?? (products[0] ? products[0].id : '')
  );
  const [quantity, setQuantity] = useState<string>('1');
  const [clientWarning, setClientWarning] = useState<string | null>(null);

  // Sync initialSkuId if products load asynchronously
  useEffect(() => {
    if (initialSkuId !== undefined && products.some((p) => p.id === initialSkuId)) {
      setSelectedSkuId(initialSkuId);
    } else if (selectedSkuId === '' && products.length > 0 && products[0]) {
      setSelectedSkuId(products[0].id);
    }
  }, [initialSkuId, products, selectedSkuId]);

  // Find currently selected product object
  const selectedProduct = products.find((p) => p.id === Number(selectedSkuId));

  // Reactive stock warning calculation
  useEffect(() => {
    if (!selectedProduct) {
      setClientWarning(null);
      return;
    }

    const numQuantity = parseInt(quantity, 10);
    if (!isNaN(numQuantity) && numQuantity > selectedProduct.current_stock) {
      setClientWarning(
        `Warning: Requested quantity (${numQuantity}) exceeds currently available stock (${selectedProduct.current_stock}) for ${selectedProduct.sku}.`
      );
    } else {
      setClientWarning(null);
    }
  }, [quantity, selectedProduct]);

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
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 rounded-xl border border-slate-800 bg-slate-900/90 p-6 sm:p-8 shadow-2xl backdrop-blur-md">
      <div>
        <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
          <span>📤</span> Log Outbound Stock Exit / Consumption
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Record stock leaving TrackFlow warehouses for carrier dispatch or internal consumption.
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
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 disabled:opacity-50 transition-all font-medium"
        >
          {products.length === 0 ? (
            <option value="">No products available</option>
          ) : (
            products.map((product) => (
              <option key={product.id} value={product.id}>
                {product.name} ({product.sku}) — {product.warehouse_id} (Stock: {product.current_stock})
              </option>
            ))
          )}
        </select>
      </div>

      {/* Reactive Stock Display Panel */}
      {selectedProduct && (
        <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="text-xs text-slate-400 font-medium">Selected Product SKU:</span>
            <p className="text-sm font-bold text-white font-mono">{selectedProduct.sku} — {selectedProduct.name}</p>
            <span className="text-xs text-slate-500">Warehouse: {selectedProduct.warehouse_id}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-300">Available Stock:</span>
            <StockStatusBadge
              currentStock={selectedProduct.current_stock}
              lowStockThreshold={selectedProduct.low_stock_threshold}
            />
          </div>
        </div>
      )}

      {/* Quantity Input Field */}
      <div className="space-y-2">
        <label htmlFor={quantityInputId} className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
          Exit Quantity
        </label>
        <input
          id={quantityInputId}
          type="number"
          min="1"
          step="1"
          value={quantity}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQuantity(e.target.value)}
          disabled={isSubmitting || !selectedProduct}
          placeholder="e.g. 5"
          required
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm font-mono text-white outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 disabled:opacity-50 transition-all"
        />
      </div>

      {/* Client-Side Stock Warning Banner */}
      {clientWarning && (
        <div className="rounded-lg bg-amber-950/80 p-4 text-xs text-amber-200 border border-amber-800/80 flex items-center gap-3 shadow-md">
          <span className="text-base">⚠️</span>
          <span>{clientWarning}</span>
        </div>
      )}

      {/* Inline Server API 400 Error Box */}
      {apiError && (
        <div className="rounded-lg bg-red-950/90 p-4 text-xs text-red-200 border border-red-800 flex items-center gap-3 shadow-md">
          <span className="text-base">🚨</span>
          <div>
            <span className="font-bold">API Validation Error:</span> {apiError}
          </div>
        </div>
      )}

      {/* Submit Button */}
      <div className="pt-2">
        <button
          type="submit"
          disabled={isSubmitting || !selectedProduct || parseInt(quantity, 10) <= 0}
          className="w-full rounded-lg bg-sky-600 hover:bg-sky-500 py-3.5 px-6 text-sm font-bold text-white shadow-lg shadow-sky-950/50 transition-all disabled:opacity-50 shrink-0"
        >
          {isSubmitting ? 'Processing Outbound Order...' : 'Confirm Outbound Order'}
        </button>
      </div>
    </form>
  );
}

export default OutboundOrderForm;
