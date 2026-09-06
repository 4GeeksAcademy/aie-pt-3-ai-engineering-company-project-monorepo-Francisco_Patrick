import React from 'react';

export default function SuppliersLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-6 w-full h-full">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Directorio de Proveedores</h1>
          <p className="text-slate-400 mt-1">Gestiona los transportistas, sus tarifas y estado operativo.</p>
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {children}
      </div>
    </div>
  );
}
