"use client";
import React, { useState } from 'react';

interface SupplierFormProps {
  onSuccess: () => void;
}

export default function SupplierForm({ onSuccess }: SupplierFormProps) {
  const [name, setName] = useState('');
  const [country, setCountry] = useState('');
  const [categories, setCategories] = useState('');
  const [costPerKg, setCostPerKg] = useState('');
  const [status, setStatus] = useState('active');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    try {
      const payload = {
        name,
        country,
        categories: categories.split(',').map(c => c.trim()).filter(Boolean),
        cost_per_kg: parseFloat(costPerKg),
        status
      };
      
      const res = await fetch('http://localhost:8000/api/suppliers/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail?.[0]?.msg || data.detail || 'Error creando proveedor');
      }
      
      setName('');
      setCountry('');
      setCategories('');
      setCostPerKg('');
      setStatus('active');
      onSuccess();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 mb-8">
      <h2 className="text-xl font-semibold text-white mb-4">Añadir Nuevo Proveedor</h2>
      {error && <div className="mb-4 p-3 bg-red-900/50 border border-red-500/50 text-red-200 rounded-lg">{error}</div>}
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Nombre</label>
            <input required type="text" value={name} onChange={e => setName(e.target.value)} className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Ej. FedEx" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">País</label>
            <input required type="text" value={country} onChange={e => setCountry(e.target.value)} className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Ej. Spain" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Categorías (separadas por coma)</label>
            <input type="text" value={categories} onChange={e => setCategories(e.target.value)} className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Ej. express, standard" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Tarifa (coste por kg)</label>
            <input required type="number" step="0.01" min="0.01" value={costPerKg} onChange={e => setCostPerKg(e.target.value)} className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Ej. 4.50" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Estado</label>
            <select value={status} onChange={e => setStatus(e.target.value)} className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="active">Activo</option>
              <option value="suspended">Suspendido</option>
            </select>
          </div>
        </div>
        <div className="flex justify-end pt-2">
          <button type="submit" disabled={loading} className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 rounded-lg font-medium transition-colors disabled:opacity-50">
            {loading ? 'Guardando...' : 'Registrar Proveedor'}
          </button>
        </div>
      </form>
    </div>
  );
}
