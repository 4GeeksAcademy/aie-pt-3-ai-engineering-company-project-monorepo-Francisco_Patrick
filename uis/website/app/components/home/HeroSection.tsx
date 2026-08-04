import React from 'react';
import Link from 'next/link';
import { MetricsAside } from './MetricsAside';

/**
 * Hero section component highlighting TrackFlow's dual-hub logistics value proposition.
 *
 * @returns JSX element rendering the main hero banner section
 */
export function HeroSection(): React.ReactElement {
  return (
    <section
      className="relative overflow-hidden border-b border-slate-800"
      aria-labelledby="hero-title"
    >
      <div
        className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(45,212,191,0.2),transparent_40%),radial-gradient(circle_at_80%_0%,rgba(56,189,248,0.18),transparent_35%)]"
        aria-hidden="true"
      />
      <div className="relative mx-auto grid w-full max-w-6xl gap-10 px-4 py-14 sm:px-6 sm:py-20 lg:grid-cols-2 lg:items-center lg:gap-14 lg:px-8 lg:py-24">
        <div>
          <p className="mb-4 inline-block rounded-full border border-cyan-300/40 bg-cyan-300/10 px-4 py-1 text-xs uppercase tracking-[0.18em] text-cyan-200">
            US + ES Logistics Platform
          </p>
          <h1
            id="hero-title"
            className="text-3xl font-semibold leading-tight text-slate-100 sm:text-4xl lg:text-5xl"
          >
            Digitaliza tu operación logística con visibilidad total de
            inventario, entregas y devoluciones.
          </h1>
          <p className="mt-5 max-w-xl text-sm leading-7 text-slate-300 sm:text-base">
            TrackFlow ayuda a marcas e-commerce a operar con precisión en
            Estados Unidos y España. Unificamos almacenes, transportistas y
            atención al cliente para reducir incidencias, acelerar entregas y
            mejorar la experiencia final.
          </p>
          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/application"
              className="rounded-md bg-cyan-400 px-5 py-3 text-center text-sm font-semibold text-slate-950 hover:bg-cyan-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-100"
            >
              Aplicar ahora
            </Link>
            <Link
              href="/#contacto"
              className="rounded-md bg-cyan-400 px-5 py-3 text-center text-sm font-semibold text-slate-950 hover:bg-cyan-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-100"
            >
              Solicitar demo
            </Link>
            <Link
              href="/#como-funciona"
              className="rounded-md border border-slate-600 px-5 py-3 text-center text-sm font-semibold text-slate-100 hover:border-slate-400 hover:bg-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"
            >
              Ver cómo funciona
            </Link>
          </div>
        </div>

        <MetricsAside />
      </div>
    </section>
  );
}
