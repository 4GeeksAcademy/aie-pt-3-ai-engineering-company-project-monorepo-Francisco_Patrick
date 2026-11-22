'use client';

import React, { useState } from 'react';
import type {
  ApprovalDecision,
  ApprovalStatus,
  DepartmentId,
  DepartmentSectionDTO,
  ResumeDecisionRequestDTO,
  ResumeDecisionResponseDTO,
} from '@repo/shared-types';

/**
 * Props for the DepartmentApprovalPanel component.
 */
export interface DepartmentApprovalPanelProps {
  /** UUID of the RFP ticket under review. */
  ticketId: string;
  /** List of active department sections with draft content and evaluation outcomes. */
  sections: DepartmentSectionDTO[];
  /** Optional callback fired when a decision is submitted (`approve`, `reject`, `request_changes`). */
  onSubmitDecision?: (payload: ResumeDecisionRequestDTO) => Promise<ResumeDecisionResponseDTO | void>;
  /** Optional callback fired after a decision completes so the parent page can refresh state. */
  onDecisionRecorded?: () => void;
}

const DEFAULT_LEADS: Record<DepartmentId, string> = {
  warehouse: 'Ana Whitfield',
  lastmile: 'Carlos Vega',
  reverse: 'Sofía Ramos',
};

/**
 * Renders the human-readable badge for a section's approval status.
 *
 * @param status - Current approval status value (`pending`, `approved`, `rejected`, `changes_requested`, `needs_human_review`).
 * @returns JSX element displaying the formatted status badge.
 */
export function renderApprovalBadge(status: ApprovalStatus): React.ReactElement {
  switch (status) {
    case 'approved':
      return (
        <span
          data-testid="approval-status-badge"
          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
        >
          Approved
        </span>
      );
    case 'rejected':
      return (
        <span
          data-testid="approval-status-badge"
          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30"
        >
          Rejected
        </span>
      );
    case 'changes_requested':
      return (
        <span
          data-testid="approval-status-badge"
          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30"
        >
          Changes Requested
        </span>
      );
    case 'needs_human_review':
      return (
        <span
          data-testid="approval-status-badge"
          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/15 text-purple-300 border border-purple-500/30"
        >
          Escalated (Miguel Torres)
        </span>
      );
    default:
      return (
        <span
          data-testid="approval-status-badge"
          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-500/15 text-sky-300 border border-sky-500/30"
        >
          Pending Approval
        </span>
      );
  }
}

/**
 * Scoped Human-in-the-Loop (HITL) department approval cards for Ana Whitfield (`warehouse`),
 * Carlos Vega (`lastmile`), and Sofía Ramos (`reverse`).
 *
 * Allows each department lead to independently inspect their draft section, review evaluation
 * compliance badges, and submit `approve`, `request_changes` (with mandatory revision feedback),
 * or `reject` without blocking peer department leads.
 *
 * @param props - Component props containing ticket ID, department sections, and submission callbacks.
 * @returns JSX Element rendering the multi-department approval review grid.
 */
export function DepartmentApprovalPanel({
  ticketId,
  sections,
  onSubmitDecision,
  onDecisionRecorded,
}: DepartmentApprovalPanelProps): React.ReactElement {
  const [statusMap, setStatusMap] = useState<Partial<Record<DepartmentId, ApprovalStatus>>>({});
  const [activeFeedbackDept, setActiveFeedbackDept] = useState<DepartmentId | null>(null);
  const [feedbackMap, setFeedbackMap] = useState<Partial<Record<DepartmentId, string>>>({});
  const [validationErrorMap, setValidationErrorMap] = useState<Partial<Record<DepartmentId, string>>>({});
  const [submittingDept, setSubmittingDept] = useState<DepartmentId | null>(null);

  const getEffectiveStatus = (section: DepartmentSectionDTO): ApprovalStatus => {
    const local = statusMap[section.department_id];
    if (local !== undefined) {
      return local;
    }
    return section.approval_status ?? 'pending';
  };

  const submitDecisionToApi = async (payload: ResumeDecisionRequestDTO): Promise<void> => {
    if (onSubmitDecision) {
      await onSubmitDecision(payload);
      return;
    }
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const response = await fetch(`${apiUrl}/api/v1/rfp/tickets/${ticketId}/resume-approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(`Error al registrar decisión para ${payload.department_id}.`);
    }
  };

  const handleDecisionClick = async (
    section: DepartmentSectionDTO,
    decision: ApprovalDecision
  ): Promise<void> => {
    const deptId = section.department_id;
    const approver = section.responsible_person || DEFAULT_LEADS[deptId];
    const feedbackText = (feedbackMap[deptId] ?? '').trim();

    if (decision === 'request_changes') {
      if (activeFeedbackDept !== deptId) {
        setActiveFeedbackDept(deptId);
        setValidationErrorMap((prev) => ({
          ...prev,
          [deptId]: 'Debe especificar instrucciones de revisión antes de solicitar cambios.',
        }));
        return;
      }
      if (feedbackText.length < 5) {
        setValidationErrorMap((prev) => ({
          ...prev,
          [deptId]: 'Las instrucciones de revisión son obligatorias (mínimo 5 caracteres).',
        }));
        return;
      }
    }

    setValidationErrorMap((prev) => ({ ...prev, [deptId]: '' }));
    setSubmittingDept(deptId);

    const payload: ResumeDecisionRequestDTO =
      feedbackText.length > 0
        ? {
            department_id: deptId,
            decision,
            approver,
            feedback: feedbackText,
          }
        : {
            department_id: deptId,
            decision,
            approver,
          };

    try {
      await submitDecisionToApi(payload);
      const nextStatus: ApprovalStatus =
        decision === 'approve'
          ? 'approved'
          : decision === 'reject'
            ? 'rejected'
            : 'changes_requested';

      setStatusMap((prev) => ({ ...prev, [deptId]: nextStatus }));
      if (decision === 'approve') {
        setActiveFeedbackDept(null);
      }
      if (onDecisionRecorded) {
        onDecisionRecorded();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al enviar la decisión.';
      setValidationErrorMap((prev) => ({ ...prev, [deptId]: msg }));
    } finally {
      setSubmittingDept(null);
    }
  };

  if (sections.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-xs text-slate-400">
        No hay secciones departamentales activas pendientes de aprobación.
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-base font-bold text-slate-100">
            Aprobación Departamental Independiente (Human-in-the-Loop)
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Cada responsable operativo puede revisar y aprobar su sección de forma independiente sin bloquear a otros departamentos.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {sections.map((section) => {
          const deptId = section.department_id;
          const leadName = section.responsible_person || DEFAULT_LEADS[deptId];
          const currentStatus = getEffectiveStatus(section);
          const isApproved = currentStatus === 'approved';
          const isRejected = currentStatus === 'rejected';
          const isSubmitting = submittingDept === deptId;
          const showFeedbackBox = activeFeedbackDept === deptId;
          const validationError = validationErrorMap[deptId];

          return (
            <div
              key={deptId}
              data-testid={`department-approval-card-${deptId}`}
              className="bg-slate-950/70 border border-slate-800 rounded-xl p-5 flex flex-col justify-between space-y-4"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400">
                      {deptId}
                    </span>
                    <h3 className="text-sm font-bold text-slate-100">
                      {section.department_name}
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Responsable:{' '}
                      <span className="font-semibold text-slate-200">{leadName}</span>
                    </p>
                  </div>
                  {renderApprovalBadge(currentStatus)}
                </div>

                {/* Evaluation Summary Pill */}
                {section.latest_evaluation && (
                  <div className="flex flex-wrap gap-2 text-[11px]">
                    <span
                      className={`px-2 py-0.5 rounded border ${
                        section.latest_evaluation.overall_pass
                          ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                          : 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                      }`}
                    >
                      Evaluación Automática:{' '}
                      {section.latest_evaluation.overall_pass ? 'PASS' : 'Observaciones'}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                      Iteración #{section.iteration ?? 1}
                    </span>
                  </div>
                )}

                {/* Draft Markdown Preview */}
                <div className="bg-slate-900/90 border border-slate-800/80 rounded-lg p-3.5 max-h-56 overflow-y-auto">
                  <pre className="text-xs text-slate-300 whitespace-pre-wrap font-sans leading-relaxed">
                    {section.draft_content || 'Sin borrador generado.'}
                  </pre>
                </div>

                {/* Revision Feedback Input */}
                {showFeedbackBox && !isApproved && (
                  <div className="space-y-2 pt-1">
                    <label
                      htmlFor={`feedback-input-${deptId}`}
                      className="block text-xs font-semibold text-amber-300"
                    >
                      Instrucciones de Revisión (Obligatorio para solicitar cambios)
                    </label>
                    <textarea
                      id={`feedback-input-${deptId}`}
                      data-testid={`feedback-textarea-${deptId}`}
                      rows={3}
                      value={feedbackMap[deptId] ?? ''}
                      onChange={(e) =>
                        setFeedbackMap((prev) => ({ ...prev, [deptId]: e.target.value }))
                      }
                      placeholder="Indique los ajustes de tarifas, volumen o SLA requeridos..."
                      className="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-emerald-400"
                    />
                  </div>
                )}

                {/* Validation Error Banner */}
                {validationError && (
                  <div
                    role="alert"
                    data-testid={`validation-error-${deptId}`}
                    className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/25 text-xs text-rose-300"
                  >
                    {validationError}
                  </div>
                )}
              </div>

              {/* Action Controls */}
              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800/80">
                <button
                  type="button"
                  data-testid={`approve-btn-${deptId}`}
                  disabled={isApproved || isRejected || isSubmitting}
                  onClick={() => {
                    void handleDecisionClick(section, 'approve');
                  }}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 text-slate-950 hover:bg-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Approve
                </button>

                <button
                  type="button"
                  data-testid={`request-changes-btn-${deptId}`}
                  disabled={isApproved || isRejected || isSubmitting}
                  onClick={() => {
                    void handleDecisionClick(section, 'request_changes');
                  }}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:bg-amber-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Request Changes
                </button>

                <button
                  type="button"
                  data-testid={`reject-btn-${deptId}`}
                  disabled={isApproved || isRejected || isSubmitting}
                  onClick={() => {
                    void handleDecisionClick(section, 'reject');
                  }}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 hover:bg-rose-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Reject
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
