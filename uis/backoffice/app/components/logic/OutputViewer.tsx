import React from 'react';

export interface OutputViewerProps {
  /** Title of current execution output */
  readonly title: string;
  /** Result payload to format and display */
  readonly payload: unknown;
  /** Active action identifier */
  readonly actionId: string;
}

/**
 * Output viewer component displaying business logic execution results dynamically in the DOM.
 *
 * @param props - Execution result title and payload
 * @returns JSX element rendering formatted JSON and visual summary
 */
export function OutputViewer(props: OutputViewerProps): React.ReactElement {
  const { title, payload, actionId } = props;
  const jsonString = JSON.stringify(payload, null, 2);

  const itemCount = Array.isArray(payload) ? payload.length : null;

  return (
    <section className="mt-6 rounded-xl border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
      <div className="flex flex-col gap-2 border-b border-slate-800 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <span className="inline-block rounded bg-cyan-400/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-cyan-300 font-medium">
            Acción: {actionId}
          </span>
          <h3 className="mt-1 text-base font-semibold text-slate-100">{title}</h3>
        </div>
        {itemCount !== null && (
          <div className="rounded border border-slate-700 bg-slate-950 px-3 py-1 text-xs text-slate-300">
            Elementos Retornados: <strong className="text-cyan-300">{itemCount}</strong>
          </div>
        )}
      </div>

      <div className="mt-4">
        <p className="mb-2 text-xs text-slate-400">Salida estructurada (DOM Interface Output):</p>
        <pre className="max-h-96 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-4 font-mono text-xs text-cyan-200 leading-5">
          {jsonString}
        </pre>
      </div>
    </section>
  );
}
