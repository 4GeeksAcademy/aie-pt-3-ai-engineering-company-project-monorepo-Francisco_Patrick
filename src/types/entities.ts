export type Country = "US" | "ES";

export type WarehouseCity = "Los Angeles" | "Zaragoza";

export type CarrierName =
  | "UPS"
  | "FedEx"
  | "DHL"
  | "MRW"
  | "SEUR"
  | "LocalCarrierUS"
  | "LocalCarrierES"
  | "CrossBorderExpress";

export type DeliveryStatus =
  | "pending"
  | "in_transit"
  | "delivered"
  | "failed"
  | "lost";

export type UrgencyLevel = "standard" | "express" | "same_day";

export type ReturnDecision = "approved" | "rejected" | "manual_review";

export type ReturnDisposition =
  | "restock"
  | "refurbish"
  | "discard"
  | "pending";

export type ClientType = "B2B" | "B2C";

export interface Warehouse {
  warehouseId: string;
  city: WarehouseCity;
  country: Country;
  managedBy: string;
  operatorsCount: number;
  managementSystem: "commercial_software" | "advanced_spreadsheet";
}

export interface InventoryItem {
  sku: string;
  warehouseId: string;
  stockUnits: number;
  lowStockThreshold: number;
  updatedAtISO: string;
}

export interface Carrier {
  carrierId: string;
  name: CarrierName;
  countries: Country[];
  supportsTrackingApi: boolean;
  onTimeRate: number;
  incidentsPer100Shipments: number;
  costPerKgEUR: number;
}

export interface Shipment {
  shipmentId: string;
  orderId: string;
  destinationCountry: Country;
  destinationPostalCode: string;
  carrierName: CarrierName;
  urgency: UrgencyLevel;
  weightKg: number;
  status: DeliveryStatus;
  operationalCostEUR: number;
  shippedAtISO: string;
}

export interface ReturnRequest {
  returnId: string;
  shipmentId: string;
  clientId: string;
  country: Country;
  reason: string;
  decision: ReturnDecision;
  disposition: ReturnDisposition;
  requestedAtISO: string;
  inspectedAtISO: string | null;
}

export interface CustomerSupportTicket {
  ticketId: string;
  clientType: ClientType;
  country: Country;
  channel: "email" | "whatsapp" | "phone";
  topic: "tracking" | "returns" | "billing" | "incident";
  isAutomatable: boolean;
  isResolved: boolean;
  createdAtISO: string;
}

export interface ClientContract {
  clientId: string;
  clientName: string;
  country: Country;
  annualContractValueEUR: number;
  startsAtISO: string;
  endsAtISO: string;
  renewalRiskScore: number;
}

export interface ExecutiveKpiSnapshot {
  country: Country;
  shipmentsVolume: number;
  onTimeDeliveryRate: number;
  operationalCostEUR: number;
  returnsRate: number;
  customerSatisfactionScore: number;
  generatedAtISO: string;
}