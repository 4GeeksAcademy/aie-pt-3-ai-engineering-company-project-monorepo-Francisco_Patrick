import {
  buildTrackFlowOperationsReport,
  summarizeExecutiveOperationalCost,
} from "./aggregation.js";
import { filterCarriers, filterReturnRequests, filterShipments } from "./filtering.js";
import { binarySearchIndexByField, linearSearchIndex } from "./search.js";
import { sortByField, sortByMultipleFields } from "./sorting.js";
import {
  carriers,
  clientContracts,
  executiveKpis,
  inventoryItems,
  returnRequests,
  shipments,
  warehouses,
} from "./sampleData.js";
import { validateAllTrackFlowData } from "./validation.js";

interface UIElements {
  resultNode: HTMLElement;
}

function findUIElements(): UIElements | null {
  const resultNode = document.getElementById("operation-result");
  if (resultNode === null) {
    return null;
  }

  return {
    resultNode,
  };
}

function renderResult(resultNode: HTMLElement, title: string, payload: unknown): void {
  const prettyPayload = JSON.stringify(payload, null, 2);
  resultNode.textContent = `${title}\n\n${prettyPayload}`;
}

function setupButtons(elements: UIElements): void {
  const filterShipmentButton = document.getElementById("btn-filter-shipments");
  const filterCarrierButton = document.getElementById("btn-filter-carriers");
  const filterReturnsButton = document.getElementById("btn-filter-returns");
  const sortAscButton = document.getElementById("btn-sort-asc");
  const sortDescButton = document.getElementById("btn-sort-desc");
  const sortMultiButton = document.getElementById("btn-sort-multi");
  const linearSearchButton = document.getElementById("btn-linear-search");
  const binarySearchButton = document.getElementById("btn-binary-search");
  const reportButton = document.getElementById("btn-report");
  const validationButton = document.getElementById("btn-validate");

  filterShipmentButton?.addEventListener("click", () => {
    const filtered = filterShipments(shipments, {
      destinationCountry: "ES",
      urgency: "express",
      minOperationalCostEUR: 4,
      maxOperationalCostEUR: 10,
    });
    renderResult(
      elements.resultNode,
      "Filtrado de shipments (ES + express + coste entre 4 y 10 EUR)",
      filtered,
    );
  });

  filterCarrierButton?.addEventListener("click", () => {
    const filtered = filterCarriers(carriers, {
      country: "US",
      minOnTimeRate: 0.9,
      maxIncidentsPer100Shipments: 3,
    });
    renderResult(
      elements.resultNode,
      "Filtrado de carriers (US + onTimeRate >= 0.9 + incidencias <= 3)",
      filtered,
    );
  });

  filterReturnsButton?.addEventListener("click", () => {
    const filtered = filterReturnRequests(returnRequests, {
      country: "US",
      decision: "approved",
    });
    renderResult(
      elements.resultNode,
      "Filtrado de returnRequests (US + approved)",
      filtered,
    );
  });

  sortAscButton?.addEventListener("click", () => {
    const sorted = sortByField(shipments, "operationalCostEUR", "asc");
    renderResult(elements.resultNode, "Orden ascendente por operationalCostEUR", sorted);
  });

  sortDescButton?.addEventListener("click", () => {
    const sorted = sortByField(shipments, "weightKg", "desc");
    renderResult(elements.resultNode, "Orden descendente por weightKg", sorted);
  });

  sortMultiButton?.addEventListener("click", () => {
    const sorted = sortByMultipleFields(shipments, [
      { field: "destinationCountry", direction: "asc" },
      { field: "operationalCostEUR", direction: "desc" },
    ]);
    renderResult(
      elements.resultNode,
      "Orden por multiples campos (destinationCountry asc + operationalCostEUR desc)",
      sorted,
    );
  });

  linearSearchButton?.addEventListener("click", () => {
    const index = linearSearchIndex(
      shipments,
      (shipment) => shipment.shipmentId === "sh-1003",
    );
    renderResult(
      elements.resultNode,
      "Busqueda lineal de shipmentId=sh-1003 en arreglo no ordenado",
      { index, found: index >= 0 ? shipments[index] : null },
    );
  });

  binarySearchButton?.addEventListener("click", () => {
    const sortedById = sortByField(shipments, "shipmentId", "asc");
    const index = binarySearchIndexByField(sortedById, "shipmentId", "sh-1004");
    renderResult(
      elements.resultNode,
      "Busqueda binaria de shipmentId=sh-1004 en arreglo ordenado",
      { index, found: index >= 0 ? sortedById[index] : null, sortedById },
    );
  });

  reportButton?.addEventListener("click", () => {
    const operationsReport = buildTrackFlowOperationsReport(shipments, returnRequests);
    const executiveCostSummary = summarizeExecutiveOperationalCost(executiveKpis);
    renderResult(elements.resultNode, "Reporte de agregaciones", {
      operationsReport,
      executiveCostSummary,
    });
  });

  validationButton?.addEventListener("click", () => {
    const validation = validateAllTrackFlowData({
      warehouses,
      inventoryItems,
      carriers,
      shipments,
      returnRequests,
      clientContracts,
      executiveKpis,
    });
    renderResult(elements.resultNode, "Validacion de reglas de negocio", validation);
  });
}

function bootstrapManualTestingUI(): void {
  const elements = findUIElements();
  if (elements === null) {
    return;
  }
  setupButtons(elements);
}

bootstrapManualTestingUI();