'use client';

import React, { useState } from 'react';

export interface SupplierFormData {
  name: string;
  country: string;
  categories: string[];
  cost_per_kg: number;
  status: 'active' | 'suspended';
}

interface SupplierFormProps {
  readonly onSubmit: (data: SupplierFormData) => Promise<void>;
  readonly isSubmitting: boolean;
}

export function SupplierForm({ onSubmit, isSubmitting }: SupplierFormProps): React.ReactElement {
  const [name, setName] = useState('');
  const [country, setCountry] = useState('');
  const [categoriesStr, setCategoriesStr] = useState('');
  const [cost, setCost] = useState('');
  const [status, setStatus] = useState<'active' | 'suspended'>('active');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    if (!name || !country || !categoriesStr || !cost) {
      setError('Please fill in all fields.');
      return;
    }
    
    const costNum = parseFloat(cost);
    if (isNaN(costNum) || costNum <= 0) {
      setError('Cost per kg must be a positive number.');
      return;
    }
    
    const categories = categoriesStr.split(',').map(c => c.trim()).filter(c => c.length > 0);
    if (categories.length === 0) {
      setError('At least one category is required.');
      return;
    }
    
    try {
      await onSubmit({
        name,
        country,
        categories,
        cost_per_kg: costNum,
        status,
      });
      // Reset form
      setName('');
      setCountry('');
      setCategoriesStr('');
      setCost('');
      setStatus('active');
    } catch (err: any) {
      setError(err.message || 'An error occurred while saving.');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-lg border border-slate-800 bg-slate-900/50 p-5">
      <h3 className="text-lg font-medium text-slate-200">Register New Supplier</h3>
      
      {error && (
        <div className="rounded bg-red-900/50 p-3 text-sm text-red-200 border border-red-800">
          {error}
        </div>
      )}
      
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Name</label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-500"
            placeholder="e.g. UPS"
          />
        </div>
        
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Country</label>
          <input
            type="text"
            value={country}
            onChange={e => setCountry(e.target.value)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-500"
            placeholder="e.g. United States"
          />
        </div>
        
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Categories (comma sep)</label>
          <input
            type="text"
            value={categoriesStr}
            onChange={e => setCategoriesStr(e.target.value)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-500"
            placeholder="e.g. express, heavy"
          />
        </div>
        
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Cost/kg ($)</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            value={cost}
            onChange={e => setCost(e.target.value)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-500"
            placeholder="0.00"
          />
        </div>
        
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Status</label>
          <select
            value={status}
            onChange={e => setStatus(e.target.value as 'active' | 'suspended')}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-500"
          >
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
          </select>
        </div>
      </div>
      
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
        >
          {isSubmitting ? 'Registering...' : 'Register Supplier'}
        </button>
      </div>
    </form>
  );
}
