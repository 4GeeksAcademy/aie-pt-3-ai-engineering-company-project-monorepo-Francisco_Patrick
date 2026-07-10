import type {
  Country,
  ExecutiveKpiSnapshot,
  ReturnRequest,
  Shipment,
} from "../types/entities.js";

export interface NumericSummary {
  total: number;
  average: number;
  min: number;
  max: number;
}

export function countByCategory<T, K extends string | number>(
  items: T[],
  categorySelector: (item: T) => K,
): Record<string, number> {
  return items.reduce<Record<string, number>>(
    (accumulator: Record<string, number>, item: T) => {
      const key = String(categorySelector(item));
      const currentValue = accumulator[key] ?? 0;
      return {
        ...accumulator,
        [key]: currentValue + 1,
      };
    },
    {},
  );
}

export function summarizeNumbers(values: number[]): NumericSummary {
  if (values.length === 0) {
    return {
      total: 0,
      average: 0,
      min: 0,
      max: 0,
    };
  }

  const total = values.reduce((sum: number, value: number) => sum + value, 0);
  const min = Math.min(...values);
  const max = Math.max(...values);

  return {
    total,
    average: total / values.length,
    min,
    max,
  };
}

export interface TrackFlowOperationsReport {
  shipmentsByStatus: Record<string, number>;
  returnsByDecision: Record<string, number>;
  operationalCostSummaryEUR: NumericSummary;
  deliveryWeightSummaryKg: NumericSummary;
  returnsRateByCountry: Record<Country, number>;
}

export function buildTrackFlowOperationsReport(
  shipments: Shipment[],
  returnRequests: ReturnRequest[],
): TrackFlowOperationsReport {
  const shipmentsByStatus = countByCategory(
    shipments,
    (shipment: Shipment) => shipment.status,
  );

  const returnsByDecision = countByCategory(
    returnRequests,
    (request: ReturnRequest) => request.decision,
  );

  const operationalCostSummaryEUR = summarizeNumbers(
    shipments.map((shipment: Shipment) => shipment.operationalCostEUR),
  );

  const deliveryWeightSummaryKg = summarizeNumbers(
    shipments.map((shipment: Shipment) => shipment.weightKg),
  );

  const countries: Country[] = ["US", "ES"];
  const returnsRateByCountry = countries.reduce<Record<Country, number>>(
    (accumulator: Record<Country, number>, country: Country) => {
      const shipmentsByCountry = shipments.filter(
        (shipment: Shipment) => shipment.destinationCountry === country,
      ).length;
      const returnsByCountry = returnRequests.filter(
        (request: ReturnRequest) => request.country === country,
      ).length;
      const rate =
        shipmentsByCountry === 0 ? 0 : returnsByCountry / shipmentsByCountry;

      return {
        ...accumulator,
        [country]: rate,
      };
    },
    {
      US: 0,
      ES: 0,
    },
  );

  return {
    shipmentsByStatus,
    returnsByDecision,
    operationalCostSummaryEUR,
    deliveryWeightSummaryKg,
    returnsRateByCountry,
  };
}

export function summarizeExecutiveOperationalCost(
  snapshots: ExecutiveKpiSnapshot[],
): NumericSummary {
  return summarizeNumbers(
    snapshots.map((snapshot: ExecutiveKpiSnapshot) => snapshot.operationalCostEUR),
  );
}