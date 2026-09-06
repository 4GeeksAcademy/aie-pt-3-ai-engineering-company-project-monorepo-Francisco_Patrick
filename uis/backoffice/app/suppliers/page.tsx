"use client";
import React, { useEffect, useState } from 'react';
import SupplierForm from '../../components/SupplierForm';
import SupplierTable from '../../components/SupplierTable';

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState([]);
  const [showForm, setShowForm] = useState(false);
  
  const [countryFilter, setCountryFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  const fetchSuppliers = async () => {
    try {
      const params = new URLSearchParams();
      if (countryFilter) params.append('country', countryFilter);
      if (categoryFilter) params.append('category', categoryFilter);
      
      const res = await fetch(`http://localhost:8000/api/suppliers/?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to fetch');
      const data = await res.json();
      setSuppliers(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchSuppliers();
  }, [countryFilter, categoryFilter]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
        <div className="flex gap-4 w-full sm:w-auto">
          <div className="flex-1 sm:flex-none">
            <label className="block text-xs font-medium text-slate-400 mb-1">Filtrar por País</label>
            <input 
              type="text" 
              placeholder="Todos los países..." 
              value={countryFilter}
              onChange={e => setCountryFilter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="flex-1 sm:flex-none">
            <label className="block text-xs font-medium text-slate-400 mb-1">Filtrar por Categoría</label>
            <input 
              type="text" 
              placeholder="Todas las categorías..." 
              value={categoryFilter}
              onChange={e => setCategoryFilter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>
        <button 
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition-colors text-sm whitespace-nowrap shadow-sm shadow-blue-900/20"
        >
          {showForm ? 'Cancelar' : '+ Nuevo Proveedor'}
        </button>
      </div>

      {showForm && (
        <SupplierForm onSuccess={() => {
          setShowForm(false);
          fetchSuppliers();
        }} />
      )}

      <SupplierTable suppliers={suppliers} onUpdate={fetchSuppliers} />
    </div>
  );
}
