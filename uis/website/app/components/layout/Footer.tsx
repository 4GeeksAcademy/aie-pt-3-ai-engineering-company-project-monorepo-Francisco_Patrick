import React from 'react';

/**
 * Corporate footer component detailing contact information, international hub locations,
 * and copyright statements.
 *
 * @returns JSX element rendering the corporate footer
 */
export function Footer(): React.ReactElement {
  return (
    <footer
      id="contacto"
      className="border-t border-slate-800 bg-slate-900"
      aria-labelledby="contacto-title"
    >
      <div className="mx-auto grid w-full max-w-6xl gap-8 px-4 py-12 sm:px-6 lg:grid-cols-2 lg:px-8">
        <section>
          <h2 id="contacto-title" className="text-2xl font-semibold text-slate-100">
            Hablemos de tu operación
          </h2>
          <p className="mt-3 max-w-lg text-sm leading-7 text-slate-300">
            Cuéntanos tus retos logísticos y te mostraremos una propuesta
            adaptada a tu volumen, mercados y objetivos de servicio.
          </p>
          <ul
            className="mt-6 space-y-2 text-sm text-slate-300"
            aria-label="Información de contacto"
          >
            <li>
              <strong className="text-slate-100">Email:</strong>{' '}
              contacto@trackflow.example
            </li>
            <li>
              <strong className="text-slate-100">Teléfono:</strong> +1 (213)
              555-0147
            </li>
            <li>
              <strong className="text-slate-100">Sedes:</strong> Los Angeles (US) y
              Zaragoza (ES)
            </li>
          </ul>
        </section>
      </div>

      <div className="border-t border-slate-800">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-2 px-4 py-4 text-xs text-slate-400 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>© 2026 TrackFlow. Todos los derechos reservados.</p>
          <p>
            Logística de última milla y gestión de almacenes para e-commerce.
          </p>
        </div>
      </div>
    </footer>
  );
}
