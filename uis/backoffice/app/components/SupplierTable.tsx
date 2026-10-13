'use client';

import React, { useState } from 'react';

export interface Supplier {
  id: number;
  name: string;
  country: string;
  categories: string[];
  cost_per_kg: number;
  status: 'active' | 'suspended';
  updated_at: string;
}

interface SupplierTableProps {
  readonly suppliers: Supplier[];
  readonly onUpdateRate: (id: number, newRate: number) => Promise<void>;
  readonly onUpdateStatus: (id: number, newStatus: 'active' | 'suspended') => Promise<void>;
  readonly onDelete: (id: number) => Promise<void>;
}

export function SupplierTable({ suppliers, onUpdateRate, onUpdateStatus, onDelete }: SupplierTableProps): React.ReactElement {
  const [editingRateId, setEditingRateId] = useState<number | null>(null);
  const [editRateValue, setEditRateValue] = useState<string>('');
  
  const handleRateSave = async (id: number) => {
    const cost = parseFloat(editRateValue);
    if (!isNaN(cost) && cost > 0) {
      await onUpdateRate(id, cost);
    }
    setEditingRateId(null);
  };
  
  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleString();
    } catch {
      return dateStr;
    }
  };

  if (suppliers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-slate-400">
        <p>No suppliers found matching the criteria.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/30">
      <table className="w-full text-left text-sm text-slate-300">
        <thead className="bg-slate-900 text-xs uppercase text-slate-400">
          <tr>
            <th className="px-4 py-3 font-medium">Supplier</th>
            <th className="px-4 py-3 font-medium">Country</th>
            <th className="px-4 py-3 font-medium">Categories</th>
            <th className="px-4 py-3 font-medium">Rate ($/kg)</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Updated</th>
            <th className="px-4 py-3 font-medium text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {suppliers.map((supplier) => (
            <tr key={supplier.id} className="hover:bg-slate-800/50">
              <td className="px-4 py-3 font-medium text-slate-200">{supplier.name}</td>
              <td className="px-4 py-3">{supplier.country}</td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {supplier.categories.map((cat, i) => (
                    <span key={i} className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                      {cat}
                    </span>
                  ))}
                </div>
              </td>
              <td className="px-4 py-3">
                {editingRateId === supplier.id ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      step="0.01"
                      className="w-20 rounded border border-slate-600 bg-slate-950 px-2 py-1 text-sm outline-none"
                      value={editRateValue}
                      onChange={(e) => setEditRateValue(e.target.value)}
                      autoFocus
                    />
                    <button onClick={() => handleRateSave(supplier.id)} className="text-cyan-400 hover:text-cyan-300">✓</button>
                    <button onClick={() => setEditingRateId(null)} className="text-slate-400 hover:text-slate-300">✕</button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span>${supplier.cost_per_kg.toFixed(2)}</span>
                    <button 
                      onClick={() => { setEditingRateId(supplier.id); setEditRateValue(supplier.cost_per_kg.toString()); }}
                      className="text-slate-500 hover:text-cyan-400"
                      title="Edit Rate"
                    >
                      ✎
                    </button>
                  </div>
                )}
              </td>
              <td className="px-4 py-3">
                <select
                  value={supplier.status}
                  onChange={(e) => onUpdateStatus(supplier.id, e.target.value as 'active' | 'suspended')}
                  className={`rounded border px-2 py-1 text-xs font-medium outline-none ${
                    supplier.status === 'active' 
                      ? 'border-emerald-900 bg-emerald-950 text-emerald-400' 
                      : 'border-red-900 bg-red-950 text-red-400'
                  }`}
                >
                  <option value="active">Active</option>
                  <option value="suspended">Suspended</option>
                </select>
              </td>
              <td className="px-4 py-3 text-xs text-slate-500">{formatDate(supplier.updated_at)}</td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={() => {
                    if (window.confirm(`Are you sure you want to delete ${supplier.name}?`)) {
                      onDelete(supplier.id);
                    }
                  }}
                  className="text-red-500 hover:text-red-400"
                  title="Delete Supplier"
                >
                  🗑️
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
