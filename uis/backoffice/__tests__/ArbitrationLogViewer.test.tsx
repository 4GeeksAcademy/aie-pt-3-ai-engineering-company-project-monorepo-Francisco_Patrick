import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import type { ArbitrationLogDTO } from '@repo/shared-types';
import { ArbitrationLogViewer } from '../components/rfp/ArbitrationLogViewer';

describe('ArbitrationLogViewer Component Tests (T030 - User Story 4)', () => {
  let container: HTMLDivElement | null = null;
  let root: Root | null = null;

  beforeAll(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  });

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    if (root && container) {
      act(() => {
        root!.unmount();
      });
      container.remove();
    }
    container = null;
    root = null;
  });

  test('T030: renders deterministic conflict arbitration timeline entries with arbiter and resolution details', () => {
    const sampleLogs: ArbitrationLogDTO[] = [
      {
        id: 'a1111111-2222-3333-4444-555555555555',
        ticket_id: 'b1111111-2222-3333-4444-555555555555',
        trigger_id: 'volume-vs-capacity',
        arbiter: 'Miguel Torres',
        rule_applied: 'Proposal volume is capped at warehouse capacity.',
        resolution_details: {
          affected_departments: ['warehouse', 'lastmile'],
          action_taken: 'Capped monthly volume at 3000 orders/month.',
          capped_volume: 3000,
          enforced_currency: null,
        },
        created_at: '2026-11-22T11:00:00Z',
      },
      {
        id: 'c1111111-2222-3333-4444-555555555555',
        ticket_id: 'b1111111-2222-3333-4444-555555555555',
        trigger_id: 'returns-sla-breach',
        arbiter: 'Sofía Ramos',
        rule_applied: 'Returns turnaround must be >= 48 hours.',
        resolution_details: {
          affected_departments: ['reverse'],
          action_taken: 'Forced request_changes on reverse section.',
          capped_volume: null,
          enforced_currency: null,
        },
        created_at: '2026-11-22T11:05:00Z',
      },
    ];

    act(() => {
      root!.render(<ArbitrationLogViewer logs={sampleLogs} />);
    });

    expect(container?.textContent).toContain('volume-vs-capacity');
    expect(container?.textContent).toContain('Miguel Torres');
    expect(container?.textContent).toContain('3000 pedidos/mes');
    expect(container?.textContent).toContain('returns-sla-breach');
    expect(container?.textContent).toContain('Sofía Ramos');
  });
});
