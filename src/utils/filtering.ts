import type { Carrier, ReturnRequest, Shipment } from "../types/entities.js";
import type {
  CarrierFilterCriteria,
  ReturnFilterCriteria,
  ShipmentFilterCriteria,
} from "../types/query.js";

export function filterShipments(
  shipments: Shipment[],
  criteria: ShipmentFilterCriteria,
): Shipment[] {
  return shipments.filter((shipment: Shipment) => {
    const matchesCountry =
      criteria.destinationCountry === undefined ||
      shipment.destinationCountry === criteria.destinationCountry;

    const matchesCarrier =
      criteria.carrierName === undefined ||
      shipment.carrierName === criteria.carrierName;

    const matchesStatus =
      criteria.status === undefined || shipment.status === criteria.status;

    const matchesUrgency =
      criteria.urgency === undefined || shipment.urgency === criteria.urgency;

    const matchesMinWeight =
      criteria.minWeightKg === undefined || shipment.weightKg >= criteria.minWeightKg;

    const matchesMaxWeight =
      criteria.maxWeightKg === undefined || shipment.weightKg <= criteria.maxWeightKg;

    const matchesMinCost =
      criteria.minOperationalCostEUR === undefined ||
      shipment.operationalCostEUR >= criteria.minOperationalCostEUR;

    const matchesMaxCost =
      criteria.maxOperationalCostEUR === undefined ||
      shipment.operationalCostEUR <= criteria.maxOperationalCostEUR;

    return (
      matchesCountry &&
      matchesCarrier &&
      matchesStatus &&
      matchesUrgency &&
      matchesMinWeight &&
      matchesMaxWeight &&
      matchesMinCost &&
      matchesMaxCost
    );
  });
}

export function filterCarriers(
  carriers: Carrier[],
  criteria: CarrierFilterCriteria,
): Carrier[] {
  return carriers.filter((carrier: Carrier) => {
    const matchesCountry =
      criteria.country === undefined || carrier.countries.includes(criteria.country);

    const matchesOnTimeRate =
      criteria.minOnTimeRate === undefined ||
      carrier.onTimeRate >= criteria.minOnTimeRate;

    const matchesIncidents =
      criteria.maxIncidentsPer100Shipments === undefined ||
      carrier.incidentsPer100Shipments <= criteria.maxIncidentsPer100Shipments;

    return matchesCountry && matchesOnTimeRate && matchesIncidents;
  });
}

export function filterReturnRequests(
  returnRequests: ReturnRequest[],
  criteria: ReturnFilterCriteria,
): ReturnRequest[] {
  return returnRequests.filter((request: ReturnRequest) => {
    const matchesCountry =
      criteria.country === undefined || request.country === criteria.country;

    const matchesDecision =
      criteria.decision === undefined || request.decision === criteria.decision;

    return matchesCountry && matchesDecision;
  });
}