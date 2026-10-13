import React from 'react';

/**
 * Experience section component highlighting TrackFlow's 24/7 cross-border logistics experience.
 *
 * @returns JSX element rendering the operational experience section
 */
export function ExperienceSection(): React.ReactElement {
  return (
    <section
      id="experiencia"
      className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6 sm:py-16 lg:px-8 lg:py-20"
      aria-labelledby="experiencia-title"
    >
      <h2 id="experiencia-title" className="text-2xl font-semibold text-slate-100 sm:text-3xl">
        Experiencia comprobada en operaciones 24/7
      </h2>
      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <article className="rounded-xl border border-slate-800 bg-slate-900 p-6">
          <h3 className="text-lg font-semibold text-slate-100">
            Equipo especializado en logística transfronteriza
          </h3>
          <p className="mt-3 text-sm leading-7 text-slate-300">
            Desde 2009, TrackFlow acompaña a marcas en la ejecución de
            operaciones entre Estados Unidos y España con trazabilidad
            completa.
          </p>
        </article>
        <article className="rounded-xl border border-slate-800 bg-slate-900 p-6">
          <h3 className="text-lg font-semibold text-slate-100">
            Arquitectura orientada a escalabilidad
          </h3>
          <p className="mt-3 text-sm leading-7 text-slate-300">
            Unificamos procesos de almacén, última milla y atención para que
            tu crecimiento comercial no rompa tu operativa.
          </p>
        </article>
      </div>
    </section>
  );
}
