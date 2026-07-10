import type {
  CarrierName,
  Country,
  DeliveryStatus,
  Shipment,
  UrgencyLevel,
} from "./entities.js";

export interface ShipmentFilterCriteria {
  destinationCountry?: Country;
  carrierName?: CarrierName;
  status?: DeliveryStatus;
  urgency?: UrgencyLevel;
  minWeightKg?: number;
  maxWeightKg?: number;
  minOperationalCostEUR?: number;
  maxOperationalCostEUR?: number;
}

export type SortDirection = "asc" | "desc";

export interface SortCriterion<T> {
  field: keyof T;
  direction: SortDirection;
}

export interface CarrierFilterCriteria {
  country?: Country;
  minOnTimeRate?: number;
  maxIncidentsPer100Shipments?: number;
}

export interface ReturnFilterCriteria {
  country?: Country;
  decision?: "approved" | "rejected" | "manual_review";
}

export interface ShipmentBinarySearchTarget {
  field: keyof Shipment;
  value: string | number;
}