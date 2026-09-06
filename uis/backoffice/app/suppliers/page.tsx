'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { SupplierTable, Supplier } from '../components/SupplierTable';
import { SupplierForm, SupplierFormData } from '../components/SupplierForm';

const API_URL = 'http://127.0.0.1:8000/suppliers';

export default function SuppliersPage(): React.ReactElement {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterCountry, setFilterCountry] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchSuppliers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filterCountry) params.append('country', filterCountry);
      if (filterCategory) params.append('category', filterCategory);
      
      const res = await fetch(`${API_URL}?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to fetch suppliers');
      
      const data = await res.json();
      setSuppliers(data);
    } catch (err: any) {
      setError(err.message || 'Error fetching suppliers');
    } finally {
      setLoading(false);
    }
  }, [filterCountry, filterCategory]);

  useEffect(() => {
    fetchSuppliers();
  }, [fetchSuppliers]);

  const handleAddSupplier = async (data: SupplierFormData) => {
    setIsSubmitting(true);
    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail?.[0]?.msg || errData.detail || 'Failed to create supplier');
      }
      
      await fetchSuppliers();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateRate = async (id: number, newRate: number) => {
    try {
      const res = await fetch(`${API_URL}/${id}/rate`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cost_per_kg: newRate }),
      });
      
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail?.[0]?.msg || errData.detail || 'Failed to update rate');
      }
      
      await fetchSuppliers();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleUpdateStatus = async (id: number, newStatus: 'active' | 'suspended') => {
    try {
      const res = await fetch(`${API_URL}/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail?.[0]?.msg || errData.detail || 'Failed to update status');
      }
      
      await fetchSuppliers();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      const res = await fetch(`${API_URL}/${id}`, {
        method: 'DELETE',
      });
      
      if (!res.ok) throw new Error('Failed to delete supplier');
      
      await fetchSuppliers();
    } catch (err: any) {
      alert(err.message);
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
              onChange={(e) => setFilterCountry(e.target.value)}
              className="rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-500"
            />
            <input
              type="text"
              placeholder="Filter by category..."
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-500"
            />
          </div>
        </div>
        
        {error && (
          <div className="rounded bg-red-900/50 p-3 text-sm text-red-200 border border-red-800">
            {error}
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
