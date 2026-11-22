import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import type {
  DepartmentSectionDTO,
  ResumeDecisionRequestDTO,
} from '@repo/shared-types';
import { DepartmentApprovalPanel } from '../components/rfp/DepartmentApprovalPanel';

describe('DepartmentApprovalPanel Component Tests (T028, T029 - User Story 4)', () => {
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

  const sampleSections: DepartmentSectionDTO[] = [
    {
      department_id: 'warehouse',
      department_name: 'Warehouse Operations',
      responsible_person: 'Ana Whitfield',
      key_aspects: { warehouse_location_preference: 'Zaragoza' },
      open_questions: [],
      policy_warnings: [],
      draft_content: '## Warehouse Proposal for ModaViva\n16.50 EUR per pallet.',
      approval_status: 'pending',
    },
    {
      department_id: 'lastmile',
      department_name: 'Last Mile and Carrier Management',
      responsible_person: 'Carlos Vega',
      key_aspects: { monthly_volume: 3000 },
      open_questions: [],
      policy_warnings: [],
      draft_content: '## Last Mile Proposal for ModaViva\n5.20 EUR per parcel.',
      approval_status: 'pending',
    },
  ];

  test('T028: renders department lead cards and submits approve decision updating badge independently', async () => {
    const submittedPayloads: ResumeDecisionRequestDTO[] = [];
    const handleDecision = async (payload: ResumeDecisionRequestDTO): Promise<void> => {
      submittedPayloads.push(payload);
    };

    act(() => {
      root!.render(
        <DepartmentApprovalPanel
          ticketId="11111111-2222-3333-4444-555555555555"
          sections={sampleSections}
          onSubmitDecision={handleDecision}
        />
      );
    });

    expect(container?.textContent).toContain('Ana Whitfield');
    expect(container?.textContent).toContain('Carlos Vega');
    expect(container?.textContent).toContain('Warehouse Proposal for ModaViva');
    expect(container?.textContent).toContain('Last Mile Proposal for ModaViva');

    const approveLastMileBtn = container?.querySelector(
      '[data-testid="approve-btn-lastmile"]'
    ) as HTMLButtonElement | null;
    expect(approveLastMileBtn).not.toBeNull();

    await act(async () => {
      approveLastMileBtn!.click();
    });

    expect(submittedPayloads).toHaveLength(1);
    expect(submittedPayloads[0]).toEqual({
      department_id: 'lastmile',
      decision: 'approve',
      approver: 'Carlos Vega',
    });

    const lmCard = container?.querySelector('[data-testid="department-approval-card-lastmile"]');
    const whCard = container?.querySelector('[data-testid="department-approval-card-warehouse"]');
    expect(lmCard?.textContent).toContain('Approved');
    expect(whCard?.textContent).toContain('Pending Approval');
  });

  test('T029: enforces non-empty revision feedback when request_changes is clicked', async () => {
    const submittedPayloads: ResumeDecisionRequestDTO[] = [];
    const handleDecision = async (payload: ResumeDecisionRequestDTO): Promise<void> => {
      submittedPayloads.push(payload);
    };

    act(() => {
      root!.render(
        <DepartmentApprovalPanel
          ticketId="11111111-2222-3333-4444-555555555555"
          sections={sampleSections}
          onSubmitDecision={handleDecision}
        />
      );
    });

    const reqChangesBtn = container?.querySelector(
      '[data-testid="request-changes-btn-warehouse"]'
    ) as HTMLButtonElement | null;
    expect(reqChangesBtn).not.toBeNull();

    // First click reveals feedback textarea and shows mandatory feedback message without submitting
    await act(async () => {
      reqChangesBtn!.click();
    });

    expect(submittedPayloads).toHaveLength(0);
    const errorBanner = container?.querySelector('[data-testid="validation-error-warehouse"]');
    expect(errorBanner?.textContent).toContain('instrucciones de revisión');

    const textarea = container?.querySelector(
      '[data-testid="feedback-textarea-warehouse"]'
    ) as HTMLTextAreaElement | null;
    expect(textarea).not.toBeNull();
  });
});
