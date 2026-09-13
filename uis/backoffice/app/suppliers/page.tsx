'use client';

import React, { useState, useEffect, useCallback } from 'react';
import type { Supplier } from '../components/SupplierTable';
import { SupplierTable } from '../components/SupplierTable';
import type { SupplierFormData } from '../components/SupplierForm';
import { SupplierForm } from '../components/SupplierForm';

const API_URL: string = 'http://127.0.0.1:8000/suppliers';

/**
 * Suppliers management page component rendering supplier form, filters, and list.
 *
 * @returns JSX Element rendering the suppliers page view.
 */
export default function SuppliersPage(): React.ReactElement {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filterCountry, setFilterCountry] = useState<string>('');
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const fetchSuppliers = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filterCountry) params.append('country', filterCountry);
      if (filterCategory) params.append('category', filterCategory);
      
      const res = await fetch(`${API_URL}?${params.toString()}`);
      if (!res.ok) {
        throw new Error('Unable to fetch suppliers list. Please check your connection or server status.');
      }
      
      const data = (await res.json()) as Supplier[];
      setSuppliers(data ?? []);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred while fetching suppliers.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [filterCountry, filterCategory]);

  useEffect(() => {
    fetchSuppliers();
  }, [fetchSuppliers]);

  const handleAddSupplier = async (data: SupplierFormData): Promise<void> => {
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const message = errData?.detail?.[0]?.msg ?? errData?.detail ?? 'Failed to create supplier';
        throw new Error(String(message));
      }
      
      await fetchSuppliers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred while creating the supplier.';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateRate = async (id: number, newRate: number): Promise<void> => {
    try {
      const res = await fetch(`${API_URL}/${id}/rate`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cost_per_kg: newRate }),
      });
      
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const message = errData?.detail?.[0]?.msg ?? errData?.detail ?? 'Failed to update rate';
        throw new Error(String(message));
      }
      
      await fetchSuppliers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update rate.';
      setError(message);
    }
  };

  const handleUpdateStatus = async (id: number, newStatus: 'active' | 'suspended'): Promise<void> => {
    try {
      const res = await fetch(`${API_URL}/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const message = errData?.detail?.[0]?.msg ?? errData?.detail ?? 'Failed to update status';
        throw new Error(String(message));
      }
      
      await fetchSuppliers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update status.';
      setError(message);
    }
  };

  const handleDelete = async (id: number): Promise<void> => {
    try {
      const res = await fetch(`${API_URL}/${id}`, {
        method: 'DELETE',
      });
      
      if (!res.ok) throw new Error('Failed to delete supplier');
      
      await fetchSuppliers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete supplier.';
      setError(message);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <SupplierForm onSubmit={handleAddSupplier} isSubmitting={isSubmitting} />
      
      <div className="flex flex-col gap-4 pt-4 border-t border-slate-800">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <h2 className="text-xl font-semibold text-slate-200">Registered Suppliers</h2>
          
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Filter by country..."
              value={filterCountry}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFilterCountry(e.target.value)}
              className="rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-500"
            />
            <input
              type="text"
              placeholder="Filter by category..."
              value={filterCategory}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFilterCategory(e.target.value)}
              className="rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-500"
            />
          </div>
        </div>
        
        {error && (
          <div className="rounded bg-red-900/50 p-4 text-sm text-red-200 border border-red-800 flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
            <button
              onClick={() => fetchSuppliers()}
              className="px-3 py-1.5 text-xs font-semibold rounded bg-red-800 hover:bg-red-700 text-white transition-all shrink-0"
            >
              🔄 Retry Loading
            </button>
          </div>
        )}
        
        {loading ? (
          <div className="flex justify-center p-8 text-slate-400">Loading suppliers...</div>
        ) : (
          <SupplierTable 
            suppliers={suppliers} 
            onUpdateRate={handleUpdateRate} 
            onUpdateStatus={handleUpdateStatus} 
            onDelete={handleDelete}
          />
        )}
      </div>
    </div>
  );
}

