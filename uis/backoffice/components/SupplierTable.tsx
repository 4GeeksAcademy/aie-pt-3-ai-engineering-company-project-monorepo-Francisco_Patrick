"use client";
import React, { useState } from 'react';

interface Supplier {
  id: number;
  name: string;
  country: string;
  categories: string[];
  cost_per_kg: number;
  status: string;
  updated_at: string;
}

interface SupplierTableProps {
  suppliers: Supplier[];
  onUpdate: () => void;
}

export default function SupplierTable({ suppliers, onUpdate }: SupplierTableProps) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editRate, setEditRate] = useState<string>('');
  
  const handleStatusToggle = async (id: number, currentStatus: string) => {
    const newStatus = currentStatus === 'active' ? 'suspended' : 'active';
    try {
      await fetch(`http://localhost:8000/api/suppliers/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });
      onUpdate();
    } catch (e) {
      console.error(e);
    }
  };

  const saveRate = async (id: number) => {
    try {
      await fetch(`http://localhost:8000/api/suppliers/${id}/rate`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cost_per_kg: parseFloat(editRate) })
      });
      setEditingId(null);
      onUpdate();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="text-xs uppercase bg-slate-950/50 text-slate-400 border-b border-slate-800">
            <tr>
              <th className="px-6 py-4 font-medium">Nombre</th>
              <th className="px-6 py-4 font-medium">País</th>
              <th className="px-6 py-4 font-medium">Categorías</th>
              <th className="px-6 py-4 font-medium">Tarifa ($/kg)</th>
              <th className="px-6 py-4 font-medium">Estado</th>
              <th className="px-6 py-4 font-medium text-right">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {suppliers.map(s => (
              <tr key={s.id} className="hover:bg-slate-800/20 transition-colors">
                <td className="px-6 py-4 font-medium text-white">{s.name}</td>
                <td className="px-6 py-4">{s.country}</td>
                <td className="px-6 py-4">
                  <div className="flex flex-wrap gap-1">
                    {s.categories.map(c => (
                      <span key={c} className="px-2 py-0.5 bg-slate-800 text-xs rounded-full">{c}</span>
                    ))}
                  </div>
                </td>
                <td className="px-6 py-4">
                  {editingId === s.id ? (
                    <div className="flex items-center gap-2">
                      <input 
                        type="number" 
                        step="0.01" 
                        value={editRate} 
                        onChange={e => setEditRate(e.target.value)}
                        className="w-20 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500"
                        autoFocus
                      />
                      <button onClick={() => saveRate(s.id)} className="text-emerald-400 hover:text-emerald-300 font-bold">✓</button>
                      <button onClick={() => setEditingId(null)} className="text-slate-500 hover:text-slate-300 font-bold">✕</button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 group">
                      <span>${s.cost_per_kg.toFixed(2)}</span>
                      <button onClick={() => { setEditingId(s.id); setEditRate(s.cost_per_kg.toString()); }} className="text-slate-600 hover:text-blue-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity">Editar</button>
                    </div>
                  )}
                </td>
                <td className="px-6 py-4">
                  <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${s.status === 'active' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                    {s.status === 'active' ? 'Activo' : 'Suspendido'}
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  <button 
                    onClick={() => handleStatusToggle(s.id, s.status)}
                    className="text-sm text-slate-400 hover:text-white transition-colors border border-slate-700 px-3 py-1 rounded-md bg-slate-800/50 hover:bg-slate-700"
                  >
                    {s.status === 'active' ? 'Suspender' : 'Activar'}
                  </button>
                </td>
              </tr>
            ))}
            {suppliers.length === 0 && (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                  No hay proveedores registrados.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
