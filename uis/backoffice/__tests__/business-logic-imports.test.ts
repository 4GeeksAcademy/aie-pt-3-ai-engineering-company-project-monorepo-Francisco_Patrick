import {
  filterCarriers,
  filterReturnRequests,
  filterShipments,
} from '../../../src/utils/filtering';
import {
  binarySearchIndexByField,
  linearSearchIndex,
} from '../../../src/utils/search';
import {
  sortByField,
  sortByMultipleFields,
} from '../../../src/utils/sorting';
import {
  buildTrackFlowOperationsReport,
  summarizeExecutiveOperationalCost,
} from '../../../src/utils/aggregation';
import { validateAllTrackFlowData } from '../../../src/utils/validation';
import {
  carriers,
  clientContracts,
  executiveKpis,
  inventoryItems,
  returnRequests,
  shipments,
  warehouses,
} from '../../../src/utils/sampleData';

describe('Business Logic Suite Module Resolution and Execution', () => {
  it('resolves filtering utilities and executes sample queries', () => {
    const filteredShipments = filterShipments(shipments, {
      destinationCountry: 'ES',
    });
    expect(Array.isArray(filteredShipments)).toBe(true);

    const filteredCarriers = filterCarriers(carriers, {
      minOnTimeRate: 0.9,
    });
    expect(Array.isArray(filteredCarriers)).toBe(true);

    const filteredReturns = filterReturnRequests(returnRequests, {
      decision: 'approved',
    });
    expect(Array.isArray(filteredReturns)).toBe(true);
  });

  it('resolves search and sorting utilities', () => {
    const sorted = sortByField(shipments, 'weightKg', 'asc');
    expect(sorted.length).toBe(shipments.length);

    const multiSorted = sortByMultipleFields(shipments, [
      { field: 'destinationCountry', direction: 'asc' },
      { field: 'weightKg', direction: 'desc' },
    ]);
    expect(multiSorted.length).toBe(shipments.length);

    const firstShipment = shipments[0];
    if (firstShipment !== undefined) {
      const targetId = firstShipment.shipmentId;
      const idx = linearSearchIndex(
        shipments,
        (s) => s.shipmentId === targetId
      );
      expect(idx).toBe(0);
    }
  });

  it('resolves aggregation and validation utilities', () => {
    const report = buildTrackFlowOperationsReport(shipments, returnRequests);
    expect(report).toBeDefined();

    const costSummary = summarizeExecutiveOperationalCost(executiveKpis);
    expect(typeof costSummary.total).toBe('number');

    const validationResult = validateAllTrackFlowData({
      shipments,
      carriers,
      warehouses,
      inventoryItems,
      returnRequests,
      clientContracts,
      executiveKpis,
    });
    expect(validationResult.isValid).toBe(true);
  });
});
