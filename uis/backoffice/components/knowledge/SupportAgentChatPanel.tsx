'use client';

/**
 * Interactive Real-Time Support Agent WebSocket Streaming Chat Panel (`SupportAgentChatPanel`).
 *
 * Renders:
 * - Connection lifecycle status indicator (`connected`, `connecting`, `reconnecting`, `unauthorized`, `disconnected`)
 *   with bound `thread_id` and progressive backoff attempt counter
 * - Multi-turn conversation timeline with live progressive token-by-token assistant bubble rendering
 * - Prominent **"Interrupt / Stop"** control during active streaming (`{"event": "interrupt"}`)
 * - Permanent **"Interrupted"** badge on preserved partial assistant responses (never deleting partial text)
 * - Instant mid-stream redirection (allowing operators to submit a new prompt while a response is streaming)
 * - Grounded policy citations, consulted sources badges, operational tool summaries, guardrail badges,
 *   and interactive `MemoryProposal` approve/reject confirmation controls.
 */

import React, { useState } from 'react';
import type {
  AgentMemoryProposalDTO,
  ChatMessageDTO,
  WebSocketChatConnectionStatus,
} from '@repo/shared-types';

/**
 * Props for `SupportAgentChatPanel`.
 */
export interface SupportAgentChatPanelProps {
  /** Chronologically ordered conversation turns. */
  messages: readonly ChatMessageDTO[];
  /** Current WebSocket connection status. */
  connectionStatus: WebSocketChatConnectionStatus;
  /** Bound conversation `thread_id`. */
  threadId: string;
  /** True while an assistant turn is actively streaming tokens. */
  isStreaming: boolean;
  /** Active unconfirmed `MemoryProposal`, if any. */
  pendingProposal: AgentMemoryProposalDTO | null;
  /** Optional sanitized error banner text. */
  errorMessage: string | null;
  /** Current progressive backoff reconnection attempt counter. */
  reconnectAttempt: number;
  /** Submit a user inquiry or mid-stream redirecting inquiry. */
  onSendMessage: (query: string) => Promise<void> | void;
  /** Immediately interrupt the active streaming assistant response. */
  onInterrupt: () => void;
  /** Manually trigger WebSocket reconnection. */
  onReconnect: () => void;
  /** Reset and start a fresh conversation thread. */
  onNewThread: () => void;
  /** Approve or reject an active `MemoryProposal`. */
  onProposalFeedback?: (action: 'approve' | 'reject') => Promise<void> | void;
}

const SAMPLE_STREAMING_PROMPTS: readonly string[] = [
  "What is TrackFlow's standard return window and who covers return shipping costs?",
  'Compare monthly pallet storage rates in Los Angeles versus Zaragoza and explain the 180-day surcharge.',
  'Which carrier is recommended for rural deliveries in Aragón and what are the standard delivery SLAs?',
];

function getConnectionBadgeConfig(
  status: WebSocketChatConnectionStatus,
  reconnectAttempt: number
): { label: string; badgeClass: string; dotClass: string } {
  switch (status) {
    case 'connected':
      return {
        label: 'WebSocket Connected • Full-Duplex Streaming',
        badgeClass: 'bg-emerald-950/80 text-emerald-300 border-emerald-800/70',
        dotClass: 'bg-emerald-400 animate-pulse',
      };
    case 'connecting':
      return {
        label: 'Connecting WebSocket...',
        badgeClass: 'bg-sky-950/80 text-sky-300 border-sky-800/70',
        dotClass: 'bg-sky-400 animate-ping',
      };
    case 'reconnecting':
      return {
        label: `Reconnecting (Attempt #${Math.max(1, reconnectAttempt)})...`,
        badgeClass: 'bg-amber-950/80 text-amber-300 border-amber-800/70',
        dotClass: 'bg-amber-400 animate-ping',
      };
    case 'unauthorized':
      return {
        label: 'Authentication Required (4001/4003)',
        badgeClass: 'bg-rose-950/80 text-rose-300 border-rose-800/70',
        dotClass: 'bg-rose-400',
      };
    case 'disconnected':
    default:
      return {
        label: 'WebSocket Disconnected • Fallback Ready',
        badgeClass: 'bg-slate-900 text-slate-300 border-slate-700',
        dotClass: 'bg-slate-400',
      };
  }
}

/**
 * Interactive Support Agent Streaming Chat Panel component.
 *
 * @param props - Chat timeline state and action callbacks.
 * @returns Rendered React element.
 */
export default function SupportAgentChatPanel({
  messages,
  connectionStatus,
  threadId,
  isStreaming,
  pendingProposal,
  errorMessage,
  reconnectAttempt,
  onSendMessage,
  onInterrupt,
  onReconnect,
  onNewThread,
  onProposalFeedback,
}: SupportAgentChatPanelProps): React.ReactElement {
  const [inputQuery, setInputQuery] = useState<string>('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const badge = getConnectionBadgeConfig(connectionStatus, reconnectAttempt);

  const handleFormSubmit = (e: React.FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    const trimmed = inputQuery.trim();
    if (trimmed.length < 2) {
      setValidationError(
        'Please enter a policy or operational question before submitting.'
      );
      return;
    }
    setValidationError(null);
    setInputQuery('');
    void onSendMessage(trimmed);
  };

  const handleSamplePromptClick = (promptText: string): void => {
    setValidationError(null);
    setInputQuery('');
    void onSendMessage(promptText);
  };

  return (
    <section
      aria-label="Support Agent Real-Time Streaming Chat"
      data-testid="support-agent-chat-panel"
      className="bg-slate-900/90 border border-slate-800 rounded-xl shadow-lg overflow-hidden"
    >
      {/* Top Status & Thread Header */}
      <div className="px-5 py-4 bg-slate-950/70 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <span
            data-testid="ws-connection-status-badge"
            className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold border ${badge.badgeClass}`}
          >
            <span className={`h-2 w-2 rounded-full ${badge.dotClass}`} />
            {badge.label}
          </span>
          <span
            data-testid="ws-bound-thread-id"
            className="text-xs font-mono text-slate-400 bg-slate-900 px-2.5 py-1 rounded border border-slate-800"
          >
            Thread: {threadId}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {connectionStatus !== 'connected' ? (
            <button
              type="button"
              data-testid="ws-reconnect-btn"
              onClick={onReconnect}
              className="text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
            >
              Reconnect
            </button>
          ) : null}
          <button
            type="button"
            data-testid="ws-new-thread-btn"
            onClick={onNewThread}
            className="text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
          >
            New Thread
          </button>
        </div>
      </div>

      {/* Quick Prompts Bar */}
      <div className="px-5 py-3 bg-slate-900/50 border-b border-slate-800/80 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Quick Streaming Prompts:
        </span>
        {SAMPLE_STREAMING_PROMPTS.map((sample, idx) => (
          <button
            key={sample}
            type="button"
            data-testid={`streaming-sample-prompt-${idx}`}
            onClick={() => handleSamplePromptClick(sample)}
            className="text-xs px-2.5 py-1 rounded-md bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700/70 transition-colors text-left"
          >
            {sample}
          </button>
        ))}
      </div>

      {/* Conversation Timeline */}
      <div
        data-testid="chat-messages-timeline"
        role="log"
        aria-live="polite"
        className="p-5 space-y-4 max-h-[540px] overflow-y-auto"
      >
        {messages.length === 0 ? (
          <div
            data-testid="chat-empty-state"
            className="text-center py-8 px-4 border border-dashed border-slate-800 rounded-xl text-slate-400 text-sm"
          >
            Ask a natural-language question about TrackFlow Delivery SLAs, Returns Policy,
            Warehouse Storage Pricing, or live Incidents &amp; Inventory Stock. Responses
            stream token-by-token in real time and can be interrupted or redirected at any
            instant.
          </div>
        ) : (
          messages.map((msg) => (
            <article
              key={msg.turn_id}
              data-testid={`chat-turn-${msg.turn_id}`}
              data-turn-role={msg.role}
              data-turn-status={msg.status}
              className={`flex flex-col ${
                msg.role === 'user' ? 'items-end' : 'items-start'
              }`}
            >
              <div
                className={`max-w-3xl rounded-xl px-4 py-3 border ${
                  msg.role === 'user'
                    ? 'bg-emerald-950/70 border-emerald-800/70 text-emerald-100'
                    : msg.status === 'interrupted'
                      ? 'bg-amber-950/30 border-amber-700/60 text-slate-100'
                      : 'bg-slate-950/80 border-slate-800 text-slate-100'
                }`}
              >
                {/* Turn Header & Status Badges */}
                <div className="flex items-center justify-between gap-3 mb-1.5 flex-wrap">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    {msg.role === 'user' ? 'Operator' : 'TrackFlow Support Agent'}
                  </span>

                  <div className="flex items-center gap-1.5 flex-wrap">
                    {msg.status === 'streaming' ? (
                      <span
                        data-testid={`turn-status-streaming-${msg.turn_id}`}
                        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-950 text-sky-300 border border-sky-800"
                      >
                        <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-ping" />
                        Streaming Live...
                      </span>
                    ) : null}

                    {msg.status === 'interrupted' ? (
                      <span
                        data-testid={`turn-status-interrupted-${msg.turn_id}`}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-950 text-amber-300 border border-amber-700"
                      >
                        Interrupted • Partial Response Preserved
                      </span>
                    ) : null}

                    {msg.status === 'completed' && msg.role === 'assistant' ? (
                      <span
                        data-testid={`turn-status-completed-${msg.turn_id}`}
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${
                          msg.is_refusal
                            ? 'bg-amber-950/80 text-amber-300 border-amber-800'
                            : 'bg-emerald-950/80 text-emerald-300 border-emerald-800'
                        }`}
                      >
                        {msg.is_refusal
                          ? 'Guardrail / Policy Refusal'
                          : 'Verified Grounded Answer'}
                      </span>
                    ) : null}

                    {msg.resolved_country ? (
                      <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-900 text-slate-300 border border-slate-700">
                        {msg.resolved_country}
                      </span>
                    ) : null}
                  </div>
                </div>

                {/* Message Text Content */}
                <div
                  data-testid={`turn-content-${msg.turn_id}`}
                  className="text-sm leading-relaxed whitespace-pre-wrap"
                >
                  {msg.content}
                  {msg.status === 'streaming' ? (
                    <span
                      aria-hidden="true"
                      className="inline-block w-2 h-4 ml-1 align-middle bg-emerald-400 animate-pulse"
                    />
                  ) : null}
                </div>

                {/* Assistant Metadata Footer (Sources, Tool Calls, Guardrails) */}
                {msg.role === 'assistant' &&
                (msg.sources.length > 0 ||
                  msg.sources_consulted.length > 0 ||
                  msg.tool_calls.length > 0 ||
                  msg.guardrail_interventions.length > 0) ? (
                  <div className="mt-3 pt-3 border-t border-slate-800/80 space-y-2">
                    {msg.sources_consulted.length > 0 ? (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-[11px] text-slate-400">
                          Sources Consulted:
                        </span>
                        {msg.sources_consulted.map((src) => (
                          <span
                            key={src}
                            data-testid={`consulted-source-badge-${src}`}
                            className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-900 text-slate-300 border border-slate-700"
                          >
                            {src}
                          </span>
                        ))}
                      </div>
                    ) : null}

                    {msg.tool_calls.length > 0 ? (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-[11px] text-slate-400">
                          Operational Tools:
                        </span>
                        {msg.tool_calls.map((tc, idx) => (
                          <span
                            key={`${tc.tool_name}-${idx}`}
                            data-testid={`tool-call-badge-${tc.tool_name}`}
                            className="px-2 py-0.5 rounded text-[11px] font-mono bg-indigo-950/80 text-indigo-300 border border-indigo-800/70"
                          >
                            {tc.tool_name} ({tc.status} • {tc.returned_count}/
                            {tc.total_matched})
                          </span>
                        ))}
                      </div>
                    ) : null}

                    {msg.sources.length > 0 ? (
                      <div className="space-y-1">
                        <span className="text-[11px] font-semibold text-slate-400">
                          Verified Policy Citations:
                        </span>
                        <div className="flex flex-wrap gap-2">
                          {msg.sources.map((cite, idx) => (
                            <div
                              key={`${cite.source_document}-${cite.section}-${idx}`}
                              data-testid={`citation-badge-${cite.source_document}`}
                              className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-xs text-slate-300"
                            >
                              <span className="font-semibold text-emerald-300">
                                {cite.source_document}
                              </span>{' '}
                              — {cite.section} (
                              {Math.round(cite.similarity_score * 100)}% match)
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </article>
          ))
        )}
      </div>

      {/* Pending Memory Proposal Banner */}
      {pendingProposal ? (
        <div
          data-testid="pending-memory-proposal-card"
          className="mx-5 mb-4 p-3.5 rounded-xl bg-indigo-950/60 border border-indigo-800/80 flex flex-wrap items-center justify-between gap-3"
        >
          <div className="space-y-0.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-300">
              Candidate Operational Memory Proposal ({pendingProposal.category} •{' '}
              {pendingProposal.target_entity})
            </span>
            <p className="text-xs text-slate-200">{pendingProposal.summary}</p>
          </div>
          {onProposalFeedback ? (
            <div className="flex items-center gap-2">
              <button
                type="button"
                data-testid="approve-memory-proposal-btn"
                onClick={() => void onProposalFeedback('approve')}
                className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white transition-colors"
              >
                Approve &amp; Persist
              </button>
              <button
                type="button"
                data-testid="reject-memory-proposal-btn"
                onClick={() => void onProposalFeedback('reject')}
                className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
              >
                Discard
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* Error Banner */}
      {errorMessage ? (
        <div
          role="alert"
          data-testid="chat-error-alert"
          className="mx-5 mb-4 p-3 rounded-lg bg-rose-950/70 border border-rose-800 text-xs text-rose-200"
        >
          {errorMessage}
        </div>
      ) : null}

      {/* Input & Interrupt / Redirect Controls */}
      <form
        onSubmit={handleFormSubmit}
        className="p-4 bg-slate-950/80 border-t border-slate-800 space-y-2"
      >
        <div className="flex flex-col sm:flex-row gap-2">
          <label htmlFor="support-agent-chat-input" className="sr-only">
            Ask the TrackFlow Support Agent
          </label>
          <input
            id="support-agent-chat-input"
            data-testid="support-agent-chat-input"
            type="text"
            value={inputQuery}
            onChange={(e) => {
              setInputQuery(e.target.value);
              if (validationError) {
                setValidationError(null);
              }
            }}
            placeholder={
              isStreaming
                ? 'Type a new question to interrupt & redirect immediately...'
                : 'Ask a policy, SLA, ticket, or inventory question...'
            }
            className="flex-1 rounded-lg bg-slate-900 border border-slate-700 px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />

          <div className="flex items-center gap-2">
            {isStreaming ? (
              <button
                type="button"
                data-testid="interrupt-generation-btn"
                onClick={onInterrupt}
                className="px-4 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider bg-amber-600 hover:bg-amber-500 text-slate-950 transition-colors"
              >
                Interrupt / Stop
              </button>
            ) : null}

            <button
              type="submit"
              data-testid="send-chat-message-btn"
              className="px-5 py-2.5 rounded-lg text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-colors"
            >
              {isStreaming ? 'Redirect Now' : 'Send'}
            </button>
          </div>
        </div>

        {validationError ? (
          <p
            role="alert"
            data-testid="chat-input-validation-error"
            className="text-xs text-amber-400"
          >
            {validationError}
          </p>
        ) : null}
      </form>
    </section>
  );
}
