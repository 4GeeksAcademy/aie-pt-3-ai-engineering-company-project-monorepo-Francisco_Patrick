'use client';

import React, { useState } from 'react';

export interface ApplicationFormData {
  readonly fullName: string;
  readonly workEmail: string;
  readonly companyName: string;
  readonly jobTitle: string;
  readonly primaryMarket: string;
  readonly monthlyOrders: string;
  readonly services: readonly string[];
  readonly launchTimeline: string;
  readonly operationSummary: string;
  readonly consent: boolean;
}

export interface FormErrors {
  readonly fullName?: string;
  readonly workEmail?: string;
  readonly companyName?: string;
  readonly jobTitle?: string;
  readonly primaryMarket?: string;
  readonly monthlyOrders?: string;
  readonly services?: string;
  readonly launchTimeline?: string;
  readonly operationSummary?: string;
  readonly consent?: string;
}

const INITIAL_FORM_DATA: ApplicationFormData = {
  fullName: '',
  workEmail: '',
  companyName: '',
  jobTitle: '',
  primaryMarket: '',
  monthlyOrders: '',
  services: [],
  launchTimeline: '',
  operationSummary: '',
  consent: false,
};

/**
 * Interactive Client Component application intake form with field validations and accessibility attributes.
 *
 * @returns JSX element rendering the application intake form
 */
export function ApplicationForm(): React.ReactElement {
  const [formData, setFormData] = useState<ApplicationFormData>(INITIAL_FORM_DATA);
  const [errors, setErrors] = useState<FormErrors>({});
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [isSuccess, setIsSuccess] = useState<boolean>(false);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ): void => {
    const { name, value, type } = e.target;
    if (type === 'checkbox') {
      const target = e.target as HTMLInputElement;
      if (name === 'consent') {
        setFormData((prev) => ({ ...prev, consent: target.checked }));
      } else if (name === 'services') {
        const selected = target.value;
        setFormData((prev) => {
          const currentServices = prev.services;
          const nextServices = target.checked
            ? [...currentServices, selected]
            : currentServices.filter((s) => s !== selected);
          return { ...prev, services: nextServices };
        });
      }
    } else {
      setFormData((prev) => ({ ...prev, [name]: value }));
    }
  };

  const validate = (): FormErrors => {
    const newErrors: Record<string, string> = {};

    if (formData.fullName.trim() === '') {
      newErrors['fullName'] = 'El nombre completo es obligatorio.';
    }

    if (formData.workEmail.trim() === '') {
      newErrors['workEmail'] = 'El email corporativo es obligatorio.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.workEmail)) {
      newErrors['workEmail'] = 'Introduce una dirección de correo válida.';
    }

    if (formData.companyName.trim() === '') {
      newErrors['companyName'] = 'El nombre de la empresa es obligatorio.';
    }

    if (formData.jobTitle.trim() === '') {
      newErrors['jobTitle'] = 'El cargo es obligatorio.';
    }

    if (formData.primaryMarket === '') {
      newErrors['primaryMarket'] = 'Selecciona un mercado principal.';
    }

    const orders = Number(formData.monthlyOrders);
    if (formData.monthlyOrders === '' || Number.isNaN(orders) || orders < 100 || orders > 1000000) {
      newErrors['monthlyOrders'] = 'Introduce un valor entre 100 y 1.000.000 pedidos.';
    }

    if (formData.services.length === 0) {
      newErrors['services'] = 'Selecciona al menos un servicio prioritario.';
    }

    if (formData.launchTimeline === '') {
      newErrors['launchTimeline'] = 'Selecciona un timeline de implementación.';
    }

    if (formData.operationSummary.trim() === '') {
      newErrors['operationSummary'] = 'Describe brevemente tu operación actual.';
    }

    if (!formData.consent) {
      newErrors['consent'] = 'Debes aceptar los términos para enviar la solicitud.';
    }

    return newErrors;
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    const validationErrors = validate();
    setErrors(validationErrors);

    if (Object.keys(validationErrors).length === 0) {
      setIsSuccess(true);
      setStatusMessage('¡Solicitud enviada con éxito! Nos pondremos en contacto pronto.');
      setFormData(INITIAL_FORM_DATA);
    } else {
      setIsSuccess(false);
      setStatusMessage('Por favor, corrige los errores destacados en el formulario.');
    }
  };

  const handleReset = (): void => {
    setFormData(INITIAL_FORM_DATA);
    setErrors({});
    setStatusMessage('');
  };

  return (
    <form id="application-form" className="mt-6 space-y-5" onSubmit={handleSubmit} noValidate>
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="fullName" className="mb-1 block text-sm font-medium text-slate-200">
            Nombre completo
          </label>
          <input
            id="fullName"
            name="fullName"
            type="text"
            autoComplete="name"
            required
            value={formData.fullName}
            onChange={handleChange}
            className="w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/40"
            aria-describedby="fullName-error"
          />
          {errors.fullName !== undefined && (
            <p id="fullName-error" className="mt-1 text-xs text-rose-300" role="alert">
              {errors.fullName}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="workEmail" className="mb-1 block text-sm font-medium text-slate-200">
            Email corporativo
          </label>
          <input
            id="workEmail"
            name="workEmail"
            type="email"
            autoComplete="email"
            required
            value={formData.workEmail}
            onChange={handleChange}
            className="w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/40"
            aria-describedby="workEmail-error workEmail-help"
          />
          <p id="workEmail-help" className="mt-1 text-xs text-slate-400">
            Aceptamos dominios corporativos.
          </p>
          {errors.workEmail !== undefined && (
            <p id="workEmail-error" className="mt-1 text-xs text-rose-300" role="alert">
              {errors.workEmail}
            </p>
          )}
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="companyName" className="mb-1 block text-sm font-medium text-slate-200">
            Empresa
          </label>
          <input
            id="companyName"
            name="companyName"
            type="text"
            autoComplete="organization"
            required
            value={formData.companyName}
            onChange={handleChange}
            className="w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/40"
            aria-describedby="companyName-error"
          />
          {errors.companyName !== undefined && (
            <p id="companyName-error" className="mt-1 text-xs text-rose-300" role="alert">
              {errors.companyName}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="jobTitle" className="mb-1 block text-sm font-medium text-slate-200">
            Cargo
          </label>
          <input
            id="jobTitle"
            name="jobTitle"
            type="text"
            autoComplete="organization-title"
            required
            value={formData.jobTitle}
            onChange={handleChange}
            className="w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/40"
            aria-describedby="jobTitle-error"
          />
          {errors.jobTitle !== undefined && (
            <p id="jobTitle-error" className="mt-1 text-xs text-rose-300" role="alert">
              {errors.jobTitle}
            </p>
          )}
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="primaryMarket" className="mb-1 block text-sm font-medium text-slate-200">
            Mercado principal
          </label>
          <select
            id="primaryMarket"
            name="primaryMarket"
            required
            value={formData.primaryMarket}
            onChange={handleChange}
            className="w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/40"
            aria-describedby="primaryMarket-error"
          >
            <option value="">Selecciona una opción</option>
            <option value="US">Estados Unidos</option>
            <option value="ES">España</option>
            <option value="US-ES">Estados Unidos y España</option>
          </select>
          {errors.primaryMarket !== undefined && (
            <p id="primaryMarket-error" className="mt-1 text-xs text-rose-300" role="alert">
              {errors.primaryMarket}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="monthlyOrders" className="mb-1 block text-sm font-medium text-slate-200">
            Pedidos mensuales
          </label>
          <input
            id="monthlyOrders"
            name="monthlyOrders"
            type="number"
            min="100"
            max="1000000"
            required
            value={formData.monthlyOrders}
            onChange={handleChange}
            className="w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/40"
            aria-describedby="monthlyOrders-help monthlyOrders-error"
          />
          <p id="monthlyOrders-help" className="mt-1 text-xs text-slate-400">
            Entre 100 y 1.000.000 pedidos mensuales.
          </p>
          {errors.monthlyOrders !== undefined && (
            <p id="monthlyOrders-error" className="mt-1 text-xs text-rose-300" role="alert">
              {errors.monthlyOrders}
            </p>
          )}
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <fieldset className="rounded-md border border-slate-700 p-4" aria-describedby="services-error">
          <legend className="px-1 text-sm font-medium text-slate-200">Servicios prioritarios</legend>
          <div className="mt-3 space-y-3 text-sm text-slate-300">
            <label className="flex items-start gap-3">
              <input
                id="serviceInventory"
                name="services"
                type="checkbox"
                value="inventory"
                checked={formData.services.includes('inventory')}
                onChange={handleChange}
                className="mt-1 h-4 w-4 rounded border-slate-500 bg-slate-900 text-cyan-400 focus:ring-cyan-300"
              />
              <span>Inventario unificado</span>
            </label>
            <label className="flex items-start gap-3">
              <input
                id="serviceTracking"
                name="services"
                type="checkbox"
                value="tracking"
                checked={formData.services.includes('tracking')}
                onChange={handleChange}
                className="mt-1 h-4 w-4 rounded border-slate-500 bg-slate-900 text-cyan-400 focus:ring-cyan-300"
              />
              <span>Tracking de transportistas</span>
            </label>
            <label className="flex items-start gap-3">
              <input
                id="serviceReturns"
                name="services"
                type="checkbox"
                value="returns"
                checked={formData.services.includes('returns')}
                onChange={handleChange}
                className="mt-1 h-4 w-4 rounded border-slate-500 bg-slate-900 text-cyan-400 focus:ring-cyan-300"
              />
              <span>Automatización de devoluciones</span>
            </label>
          </div>
          {errors.services !== undefined && (
            <p id="services-error" className="mt-3 text-xs text-rose-300" role="alert">
              {errors.services}
            </p>
          )}
        </fieldset>

        <div>
          <label htmlFor="launchTimeline" className="mb-1 block text-sm font-medium text-slate-200">
            Timeline de implementación
          </label>
          <select
            id="launchTimeline"
            name="launchTimeline"
            required
            value={formData.launchTimeline}
            onChange={handleChange}
            className="w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/40"
            aria-describedby="launchTimeline-error"
          >
            <option value="">Selecciona una opción</option>
            <option value="0-30">0 a 30 días</option>
            <option value="31-90">31 a 90 días</option>
            <option value="90+">Más de 90 días</option>
          </select>
          {errors.launchTimeline !== undefined && (
            <p id="launchTimeline-error" className="mt-1 text-xs text-rose-300" role="alert">
              {errors.launchTimeline}
            </p>
          )}
        </div>
      </div>

      <div>
        <label htmlFor="operationSummary" className="mb-1 block text-sm font-medium text-slate-200">
          Describe tu operación actual
        </label>
        <textarea
          id="operationSummary"
          name="operationSummary"
          rows={4}
          required
          value={formData.operationSummary}
          onChange={handleChange}
          className="w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/40"
          aria-describedby="operationSummary-help operationSummary-error"
        />
        <p id="operationSummary-help" className="mt-1 text-xs text-slate-400">
          Incluye países, almacenes, retos de tracking o devoluciones y objetivo principal.
        </p>
        {errors.operationSummary !== undefined && (
          <p id="operationSummary-error" className="mt-1 text-xs text-rose-300" role="alert">
            {errors.operationSummary}
          </p>
        )}
      </div>

      <div>
        <label className="flex items-start gap-3 text-sm text-slate-300" htmlFor="consent">
          <input
            id="consent"
            name="consent"
            type="checkbox"
            required
            checked={formData.consent}
            onChange={handleChange}
            className="mt-1 h-4 w-4 rounded border-slate-500 bg-slate-900 text-cyan-400 focus:ring-cyan-300"
            aria-describedby="consent-error"
          />
          <span>
            Acepto que TrackFlow utilice esta información para contactarme sobre la evaluación de mi
            operación.
          </span>
        </label>
        {errors.consent !== undefined && (
          <p id="consent-error" className="mt-1 text-xs text-rose-300" role="alert">
            {errors.consent}
          </p>
        )}
      </div>

      {statusMessage !== '' && (
        <div
          id="form-status"
          className={`rounded-md p-3 text-sm font-medium ${
            isSuccess ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-rose-950 text-rose-300 border border-rose-800'
          }`}
          role="status"
          aria-live="polite"
        >
          {statusMessage}
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          type="submit"
          className="rounded-md bg-cyan-400 px-4 py-2.5 text-sm font-semibold text-slate-950 hover:bg-cyan-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-100"
        >
          Enviar application
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="rounded-md border border-slate-500 px-4 py-2.5 text-sm font-semibold text-slate-100 hover:border-slate-300 hover:bg-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"
        >
          Limpiar formulario
        </button>
      </div>
    </form>
  );
}
