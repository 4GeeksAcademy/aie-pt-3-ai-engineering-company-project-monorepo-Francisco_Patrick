'use client';

import React, { useState } from 'react';
import { filterCarriers, filterReturnRequests, filterShipments } from '../../../../src/utils/filtering';
import { binarySearchIndexByField, linearSearchIndex } from '../../../../src/utils/search';
import { sortByField, sortByMultipleFields } from '../../../../src/utils/sorting';
import {
  buildTrackFlowOperationsReport,
  summarizeExecutiveOperationalCost,
} from '../../../../src/utils/aggregation';
import { validateAllTrackFlowData } from '../../../../src/utils/validation';
import {
  carriers,
  clientContracts,
  executiveKpis,
  inventoryItems,
  returnRequests,
  shipments,
  warehouses,
} from '../../../../src/utils/sampleData';
import { LogicRunnerPanel, type LogicActionType } from '../components/logic/LogicRunnerPanel';
import { OutputViewer } from '../components/logic/OutputViewer';

interface ExecutionResult {
  readonly title: string;
  readonly payload: unknown;
  readonly actionId: LogicActionType;
}

/**
 * Interactive Business Logic Execution Suite page route (`/business-logic`) inside `./uis/backoffice`.
 * Directly imports and executes Milestone 2 TypeScript business logic algorithms from `src/utils/`
 * and renders outputs directly in the web UI.
 *
 * @returns JSX element rendering the business logic execution suite
 */
export default function BusinessLogicPage(): React.ReactElement {
  const [activeAction, setActiveAction] = useState<LogicActionType>('filter-shipments');
  const [result, setResult] = useState<ExecutionResult>(() => {
    const initialFiltered = filterShipments(shipments, {
      destinationCountry: 'ES',
      urgency: 'express',
      minOperationalCostEUR: 4,
      maxOperationalCostEUR: 10,
    });
    return {
      title: 'Filtrado de Shipments (ES + Express + Coste entre 4 y 10 EUR)',
      payload: initialFiltered,
      actionId: 'filter-shipments',
    };
  });

  const handleTriggerAction = (actionId: LogicActionType): void => {
    setActiveAction(actionId);

    switch (actionId) {
      case 'filter-shipments': {
        const filtered = filterShipments(shipments, {
          destinationCountry: 'ES',
          urgency: 'express',
          minOperationalCostEUR: 4,
          maxOperationalCostEUR: 10,
        });
        setResult({
          title: 'Filtrado de Shipments (ES + Express + Coste entre 4 y 10 EUR)',
          payload: filtered,
          actionId,
        });
        break;
      }
      case 'filter-carriers': {
        const filtered = filterCarriers(carriers, {
          country: 'US',
          minOnTimeRate: 0.9,
          maxIncidentsPer100Shipments: 3,
        });
        setResult({
          title: 'Filtrado de Carriers (US + SLA OnTime >= 90% + Incidencias <= 3)',
          payload: filtered,
          actionId,
        });
        break;
      }
      case 'filter-returns': {
        const filtered = filterReturnRequests(returnRequests, {
          country: 'US',
          decision: 'approved',
        });
        setResult({
          title: 'Filtrado de Devoluciones (US + Aprobadas)',
          payload: filtered,
          actionId,
        });
        break;
      }
      case 'sort-asc': {
        const sorted = sortByField(shipments, 'operationalCostEUR', 'asc');
        setResult({
          title: 'Orden Ascendente de Shipments por operationalCostEUR',
          payload: sorted,
          actionId,
        });
        break;
      }
      case 'sort-desc': {
        const sorted = sortByField(shipments, 'weightKg', 'desc');
        setResult({
          title: 'Orden Descendente de Shipments por weightKg',
          payload: sorted,
          actionId,
        });
        break;
      }
      case 'sort-multi': {
        const sorted = sortByMultipleFields(shipments, [
          { field: 'destinationCountry', direction: 'asc' },
          { field: 'operationalCostEUR', direction: 'desc' },
        ]);
        setResult({
          title: 'Orden por Múltiples Campos (destinationCountry ASC + operationalCostEUR DESC)',
          payload: sorted,
          actionId,
        });
        break;
      }
      case 'linear-search': {
        const index = linearSearchIndex(
          shipments,
          (shipment) => shipment.shipmentId === 'sh-1003',
        );
        setResult({
          title: 'Búsqueda Lineal del Shipment sh-1003 en arreglo no ordenado',
          payload: {
            targetId: 'sh-1003',
            foundIndex: index,
            foundItem: index >= 0 ? shipments[index] : null,
          },
          actionId,
        });
        break;
      }
      case 'binary-search': {
        const sortedById = sortByField(shipments, 'shipmentId', 'asc');
        const index = binarySearchIndexByField(sortedById, 'shipmentId', 'sh-1004');
        setResult({
          title: 'Búsqueda Binaria del Shipment sh-1004 en arreglo ordenado',
          payload: {
            targetId: 'sh-1004',
            foundIndex: index,
            foundItem: index >= 0 ? sortedById[index] : null,
          },
          actionId,
        });
        break;
      }
      case 'report': {
        const operationsReport = buildTrackFlowOperationsReport(shipments, returnRequests);
        const executiveCostSummary = summarizeExecutiveOperationalCost(executiveKpis);
        setResult({
          title: 'Reporte Consolidado de Agregación Operativa y Ejecutiva',
          payload: {
            operationsReport,
            executiveCostSummary,
          },
          actionId,
        });
        break;
      }
      case 'validate': {
        const validation = validateAllTrackFlowData({
          warehouses,
          inventoryItems,
          carriers,
          shipments,
          returnRequests,
          clientContracts,
          executiveKpis,
        });
        setResult({
          title: 'Auditoría Completa de Reglas de Negocio Dominio TrackFlow',
          payload: validation,
          actionId,
        });
        break;
      }
    }
  };

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
        <div className="flex flex-col gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-cyan-300">
            Milestone 2 Integration
          </span>
          <h1 className="text-2xl font-bold text-slate-100 sm:text-3xl">
            Business Logic Execution Suite
          </h1>
          <p className="text-sm text-slate-300">
            Esta interfaz importa directamente las funciones del módulo de dominio (`src/utils`) y permite ejecutar algoritmos de filtrado, ordenamiento, búsqueda, reportes y validación en tiempo real.
          </p>
        </div>
      </section>

      <LogicRunnerPanel activeAction={activeAction} onTriggerAction={handleTriggerAction} />

      <OutputViewer title={result.title} payload={result.payload} actionId={result.actionId} />
    </div>
  );
}
