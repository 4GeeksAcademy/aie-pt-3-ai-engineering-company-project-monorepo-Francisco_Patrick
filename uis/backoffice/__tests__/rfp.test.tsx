import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import type {
  ReadabilityScoresDTO,
  DepartmentSectionDTO,
  IntakeHandoffPayloadDTO,
} from '@repo/shared-types';
import { TicketStatusBadge } from '../components/rfp/TicketStatusBadge';
import { ReadabilityMetricCard } from '../components/rfp/ReadabilityMetricCard';
import { DepartmentKeyAspectsCard } from '../components/rfp/DepartmentKeyAspectsCard';
import { HandoffJsonViewer } from '../components/rfp/HandoffJsonViewer';

describe('RFP Intake & Agentic Analysis Pipeline UI Components (Phase 6)', () => {
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

  test('TicketStatusBadge renders correct status labels and colors', () => {
    act(() => {
      root!.render(
        <div>
          <TicketStatusBadge status="analizando" />
          <TicketStatusBadge status="descartado" />
          <TicketStatusBadge status="analisis_completo" />
        </div>
      );
    });

    expect(container?.textContent).toContain('Analizando');
    expect(container?.textContent).toContain('Descartado');
    expect(container?.textContent).toContain('Análisis Completo');
  });

  test('ReadabilityMetricCard renders Flesch Reading Ease and Grade Level', () => {
    const mockScores: ReadabilityScoresDTO = {
      flesch_reading_ease: 64.5,
      flesch_kincaid_grade: 8.2,
      reading_level_label: 'Standard',
      word_count: 850,
      sentence_count: 52,
    };

    act(() => {
      root!.render(<ReadabilityMetricCard scores={mockScores} />);
    });

    expect(container?.textContent).toContain('64.5');
    expect(container?.textContent).toContain('8.2');
    expect(container?.textContent).toContain('Standard');
    expect(container?.textContent).toContain('850');
  });

  test('DepartmentKeyAspectsCard renders tabs, responsible person, and open questions', () => {
    const mockSections: DepartmentSectionDTO[] = [
      {
        department_id: 'warehouse',
        department_name: 'Operaciones de Almacén',
        responsible_person: 'Ana Whitfield',
        key_aspects: {
          warehouse_location_preference: 'Zaragoza',
          pallet_storage_required: null,
        },
        open_questions: ['Número exacto de pallets no especificado.'],
        policy_warnings: [],
      },
      {
        department_id: 'reverse',
        department_name: 'Logística Inversa y Devoluciones',
        responsible_person: 'Sofía Ramos',
        key_aspects: {
          return_window_days: 30,
        },
        open_questions: ['Tasa estimada de devoluciones no informada.'],
        policy_warnings: ['Advertencia de prueba'],
      },
    ];

    act(() => {
      root!.render(<DepartmentKeyAspectsCard sections={mockSections} />);
    });

    expect(container?.textContent).toContain('Operaciones de Almacén');
    expect(container?.textContent).toContain('Logística Inversa y Devoluciones');
    expect(container?.textContent).toContain('Ana Whitfield');
    expect(container?.textContent).toContain('Número exacto de pallets no especificado.');
  });

  test('HandoffJsonViewer renders contacts and allows JSON toggle', () => {
    const mockHandoff: IntakeHandoffPayloadDTO = {
      ticket_id: 'c1f7b889-1234-4a21-99ef-8a9d0f4d3201',
      schema_version: '1.0.0',
      executive_summary: 'Briefing para Miguel Torres sobre propuesta ModaViva.',
      flagged_contradictions: [],
      key_questions_for_prospect: ['Pregunta de prueba'],
      internal_contacts: [
        {
          name: 'Miguel Torres',
          role: 'Director Comercial',
          department: 'Ventas y Alianzas',
        },
      ],
      full_handoff_json: {
        ticket_id: 'c1f7b889-1234-4a21-99ef-8a9d0f4d3201',
        schema_version: '1.0.0',
      },
      created_at: '2026-11-21T18:00:00Z',
    };

    act(() => {
      root!.render(<HandoffJsonViewer handoff={mockHandoff} />);
    });

    expect(container?.textContent).toContain('Paquete de Entrega a Parte 2');
    expect(container?.textContent).toContain('Miguel Torres');
    expect(container?.textContent).toContain('Director Comercial');
  });
});
