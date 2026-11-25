/**
 * Automated Jest unit and integration test suite for Real-Time Bidirectional WebSocket Streaming Chat
 * with True Generation Abort (Part 2).
 *
 * Covers:
 * - User Story 1 (T010): `token_chunk` frame parsing, progressive token accumulation in the active
 *   assistant bubble (`applyStreamEventToMessages`), and transition to `completed` with grounded
 *   citations, consulted sources, and tool call badges.
 * - User Story 2 (T018): Mid-response `interrupt` button click, preservation of partial text with
 *   permanent `status: "interrupted"` badge, and mid-stream redirection with a new user prompt.
 * - User Story 3 (T024): JWT token attachment in `buildSupportAgentWebSocketUrl` and immediate
 *   halt of reconnection retries on close codes `4001` and `4003` (`isPermanentAuthCloseCode`).
 * - User Story 4 (T029): Progressive exponential backoff schedule (`calculateReconnectBackoffMs`:
 *   `1000, 2000, 4000, 8000, 16000, 30000` ms) and turn deduplication by `turn_id` upon
 *   `session_rehydrated` (`mergeRehydratedMessages`).
 * - User Story 5 (T034): Strict TrackFlow Support Agent domain field alignment (`session_id`,
 *   `thread_id`, `trace_id`, `turn_id`, `sources`, `sources_consulted`, `tool_calls`,
 *   `memory_proposal`, `guardrail_interventions`, `resolved_country`) and rejection of unknown
 *   or Part 1 RFP SSE fields (`rfp_ticket_created`, `rfp_id`, `services_requested`).
 */

import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import type { ChatMessageDTO } from '@repo/shared-types';
import SupportAgentChatPanel from '../components/knowledge/SupportAgentChatPanel';
import {
  applyStreamEventToMessages,
  buildSupportAgentWebSocketUrl,
  calculateReconnectBackoffMs,
  isPermanentAuthCloseCode,
  mergeRehydratedMessages,
  parseAgentChatStreamEvent,
  serializeClientCommand,
} from '../lib/supportAgentChatClient';

describe('Support Agent Bidirectional WebSocket Streaming Chat (US1 - US5)', () => {
  // =========================================================================
  // User Story 1: Live Token Chunk Parsing & Progressive Accumulation (T010)
  // =========================================================================
  describe('US1: token_chunk frame parsing, progressive token accumulation, and completion metadata', () => {
    it('progressively accumulates token_chunk deltas into the active streaming assistant bubble and transitions to completed', () => {
      let messages: ChatMessageDTO[] = [];

      const startedFrame = parseAgentChatStreamEvent(
        JSON.stringify({
          event: 'generation_started',
          thread_id: 'thr_001',
          session_id: 'sess_001',
          turn_id: 'turn_asst_1',
          user_turn_id: 'turn_usr_1',
          query: "What is TrackFlow's standard return window?",
          sequence_id: 1,
          timestamp: '2026-11-24T21:00:00Z',
        })
      );
      expect(startedFrame).not.toBeNull();
      messages = applyStreamEventToMessages(messages, startedFrame!);
      expect(messages).toHaveLength(2);
      expect(messages[0]?.role).toBe('user');
      expect(messages[1]?.role).toBe('assistant');
      expect(messages[1]?.status).toBe('streaming');
      expect(messages[1]?.content).toBe('');

      const chunks = [
        { delta: "TrackFlow's ", accumulated: "TrackFlow's " },
        { delta: 'standard return ', accumulated: "TrackFlow's standard return " },
        {
          delta: 'window is 30 days.',
          accumulated: "TrackFlow's standard return window is 30 days.",
        },
      ];

      chunks.forEach((c, idx) => {
        const chunkEvent = parseAgentChatStreamEvent(
          JSON.stringify({
            event: 'token_chunk',
            thread_id: 'thr_001',
            session_id: 'sess_001',
            turn_id: 'turn_asst_1',
            chunk_index: idx,
            delta: c.delta,
            accumulated_content: c.accumulated,
            sequence_id: idx + 2,
            timestamp: '2026-11-24T21:00:01Z',
          })
        );
        expect(chunkEvent).not.toBeNull();
        messages = applyStreamEventToMessages(messages, chunkEvent!);
        expect(messages[1]?.status).toBe('streaming');
        expect(messages[1]?.content).toBe(c.accumulated);
      });

      const completedEvent = parseAgentChatStreamEvent(
        JSON.stringify({
          event: 'generation_completed',
          thread_id: 'thr_001',
          session_id: 'sess_001',
          turn_id: 'turn_asst_1',
          query: "What is TrackFlow's standard return window?",
          content: "TrackFlow's standard return window is 30 days.",
          status: 'completed',
          is_refusal: false,
          fallback_triggered: false,
          trace_id: 'trace_abc_123',
          node_sequence: ['intake', 'retrieval', 'generation'],
          execution_time_ms: 85.4,
          sources: [
            {
              source_document: 'returns-policy',
              section: 'Standard Return Window',
              similarity_score: 0.94,
            },
          ],
          sources_consulted: ['rag'],
          tool_calls: [
            {
              tool_name: 'ticket_tool',
              status: 'success',
              total_matched: 1,
              returned_count: 1,
              latency_ms: 12.3,
              error_message: null,
            },
          ],
          memory_proposal: null,
          recalled_memories: [],
          guardrail_interventions: [],
          resolved_country: 'US',
          sequence_id: 5,
          timestamp: '2026-11-24T21:00:02Z',
        })
      );
      expect(completedEvent).not.toBeNull();
      messages = applyStreamEventToMessages(messages, completedEvent!);

      expect(messages).toHaveLength(2);
      const assistantTurn = messages[1]!;
      expect(assistantTurn.status).toBe('completed');
      expect(assistantTurn.content).toBe(
        "TrackFlow's standard return window is 30 days."
      );
      expect(assistantTurn.trace_id).toBe('trace_abc_123');
      expect(assistantTurn.sources).toHaveLength(1);
      expect(assistantTurn.sources[0]?.source_document).toBe('returns-policy');
      expect(assistantTurn.sources_consulted).toEqual(['rag']);
      expect(assistantTurn.tool_calls).toHaveLength(1);
      expect(assistantTurn.resolved_country).toBe('US');
    });
  });

  // =========================================================================
  // User Story 2: True Generation Abort, Preserve Partial & Redirect (T018)
  // =========================================================================
  describe('US2: mid-response interrupt button, partial text preservation, and redirection', () => {
    let container: HTMLDivElement | null = null;
    let root: Root | null = null;

    beforeAll(() => {
      (
        globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
      ).IS_REACT_ACT_ENVIRONMENT = true;
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

    it('preserves partial assistant content with status="interrupted" and ignores any late trailing token chunks', () => {
      let messages: ChatMessageDTO[] = [
        {
          turn_id: 'usr_1',
          thread_id: 'thr_002',
          session_id: 'sess_002',
          role: 'user',
          content: 'Compare storage rates in LA and Zaragoza',
          status: 'completed',
          parent_user_turn_id: null,
          interrupted_reason: null,
          is_refusal: false,
          fallback_triggered: false,
          trace_id: null,
          node_sequence: [],
          execution_time_ms: 0,
          sources: [],
          sources_consulted: [],
          tool_calls: [],
          memory_proposal: null,
          recalled_memories: [],
          guardrail_interventions: [],
          resolved_country: null,
          created_at: '2026-11-24T21:01:00Z',
          updated_at: '2026-11-24T21:01:00Z',
        },
        {
          turn_id: 'asst_1',
          thread_id: 'thr_002',
          session_id: 'sess_002',
          role: 'assistant',
          content: 'In Los Angeles, pallet storage costs $18/pallet...',
          status: 'streaming',
          parent_user_turn_id: 'usr_1',
          interrupted_reason: null,
          is_refusal: false,
          fallback_triggered: false,
          trace_id: null,
          node_sequence: [],
          execution_time_ms: 0,
          sources: [],
          sources_consulted: [],
          tool_calls: [],
          memory_proposal: null,
          recalled_memories: [],
          guardrail_interventions: [],
          resolved_country: null,
          created_at: '2026-11-24T21:01:01Z',
          updated_at: '2026-11-24T21:01:01Z',
        },
      ];

      const interruptedEvent = parseAgentChatStreamEvent(
        JSON.stringify({
          event: 'generation_interrupted',
          thread_id: 'thr_002',
          session_id: 'sess_002',
          turn_id: 'asst_1',
          partial_content: 'In Los Angeles, pallet storage costs $18/pallet...',
          status: 'interrupted',
          reason: 'client_interrupt',
          sequence_id: 4,
          timestamp: '2026-11-24T21:01:02Z',
        })
      );
      expect(interruptedEvent).not.toBeNull();
      messages = applyStreamEventToMessages(messages, interruptedEvent!);

      expect(messages[1]?.status).toBe('interrupted');
      expect(messages[1]?.interrupted_reason).toBe('client_interrupt');
      expect(messages[1]?.content).toBe(
        'In Los Angeles, pallet storage costs $18/pallet...'
      );

      // Even if a hypothetical late chunk were passed to the reducer, interrupted turn is immutable
      const lateChunk = parseAgentChatStreamEvent(
        JSON.stringify({
          event: 'token_chunk',
          thread_id: 'thr_002',
          session_id: 'sess_002',
          turn_id: 'asst_1',
          chunk_index: 99,
          delta: ' TRAILING_NOISE',
          accumulated_content:
            'In Los Angeles, pallet storage costs $18/pallet... TRAILING_NOISE',
          sequence_id: 5,
          timestamp: '2026-11-24T21:01:03Z',
        })
      );
      messages = applyStreamEventToMessages(messages, lateChunk!);
      expect(messages[1]?.content).toBe(
        'In Los Angeles, pallet storage costs $18/pallet...'
      );
    });

    it('renders Interrupt / Stop button during streaming, triggers onInterrupt, and displays Interrupted badge on preserved turn', async () => {
      const handleInterrupt = jest.fn();
      const handleSend = jest.fn();

      const streamingMessages: ChatMessageDTO[] = [
        {
          turn_id: 'asst_stream_1',
          thread_id: 'thr_ui_1',
          session_id: 'sess_ui_1',
          role: 'assistant',
          content: 'Partial streaming response before user clicks stop...',
          status: 'streaming',
          parent_user_turn_id: 'usr_ui_1',
          interrupted_reason: null,
          is_refusal: false,
          fallback_triggered: false,
          trace_id: null,
          node_sequence: [],
          execution_time_ms: 0,
          sources: [],
          sources_consulted: [],
          tool_calls: [],
          memory_proposal: null,
          recalled_memories: [],
          guardrail_interventions: [],
          resolved_country: null,
          created_at: '2026-11-24T21:02:00Z',
          updated_at: '2026-11-24T21:02:00Z',
        },
      ];

      await act(async () => {
        root!.render(
          React.createElement(SupportAgentChatPanel, {
            messages: streamingMessages,
            connectionStatus: 'connected',
            threadId: 'thr_ui_1',
            isStreaming: true,
            pendingProposal: null,
            errorMessage: null,
            reconnectAttempt: 0,
            onSendMessage: handleSend,
            onInterrupt: handleInterrupt,
            onReconnect: jest.fn(),
            onNewThread: jest.fn(),
          })
        );
      });

      const interruptBtn = container?.querySelector(
        '[data-testid="interrupt-generation-btn"]'
      );
      expect(interruptBtn).not.toBeNull();

      await act(async () => {
        interruptBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });
      expect(handleInterrupt).toHaveBeenCalledTimes(1);

      // Re-render with interrupted status and a redirected turn
      const interruptedMessages: ChatMessageDTO[] = [
        {
          ...streamingMessages[0]!,
          status: 'interrupted',
          interrupted_reason: 'client_interrupt',
        },
      ];

      await act(async () => {
        root!.render(
          React.createElement(SupportAgentChatPanel, {
            messages: interruptedMessages,
            connectionStatus: 'connected',
            threadId: 'thr_ui_1',
            isStreaming: false,
            pendingProposal: null,
            errorMessage: null,
            reconnectAttempt: 0,
            onSendMessage: handleSend,
            onInterrupt: handleInterrupt,
            onReconnect: jest.fn(),
            onNewThread: jest.fn(),
          })
        );
      });

      const interruptedBadge = container?.querySelector(
        '[data-testid="turn-status-interrupted-asst_stream_1"]'
      );
      expect(interruptedBadge).not.toBeNull();
      expect(interruptedBadge?.textContent).toContain('Interrupted');
      expect(container?.textContent).toContain(
        'Partial streaming response before user clicks stop...'
      );
    });
  });

  // =========================================================================
  // User Story 3: JWT Authentication & 4001/4003 Permanent Halt (T024)
  // =========================================================================
  describe('US3: WebSocket JWT URL binding and permanent halt on 4001/4003 close codes', () => {
    it('attaches thread_id, session_id, and JWT token to the WebSocket URL and identifies 4001/4003 as permanent auth close codes', () => {
      const wsUrl = buildSupportAgentWebSocketUrl({
        apiUrl: 'http://localhost:8000',
        threadId: 'thr_auth_01',
        sessionId: 'sess_auth_01',
        token: 'jwt-secret-token-xyz',
      });

      expect(wsUrl).toBe(
        'ws://localhost:8000/api/v1/agent/ws?thread_id=thr_auth_01&session_id=sess_auth_01&token=jwt-secret-token-xyz'
      );

      expect(isPermanentAuthCloseCode(4001)).toBe(true);
      expect(isPermanentAuthCloseCode(4003)).toBe(true);
      expect(isPermanentAuthCloseCode(1008)).toBe(true);
      expect(isPermanentAuthCloseCode(1006)).toBe(false);
      expect(isPermanentAuthCloseCode(1000)).toBe(false);
    });
  });

  // =========================================================================
  // User Story 4: Exponential Backoff & Turn Deduplication (T029)
  // =========================================================================
  describe('US4: Progressive exponential backoff (1s..30s) and turn deduplication on session_rehydrated', () => {
    it('calculates progressive exponential backoff delays of 1s, 2s, 4s, 8s, 16s capped at 30s', () => {
      expect(calculateReconnectBackoffMs(0)).toBe(1000);
      expect(calculateReconnectBackoffMs(1)).toBe(2000);
      expect(calculateReconnectBackoffMs(2)).toBe(4000);
      expect(calculateReconnectBackoffMs(3)).toBe(8000);
      expect(calculateReconnectBackoffMs(4)).toBe(16000);
      expect(calculateReconnectBackoffMs(5)).toBe(30000);
      expect(calculateReconnectBackoffMs(8)).toBe(30000);
    });

    it('deduplicates rehydrated turns by turn_id while preserving both completed and interrupted turns in order', () => {
      const existingLocal: ChatMessageDTO[] = [
        {
          turn_id: 'usr_1',
          thread_id: 'thr_rehydrate',
          session_id: 'sess_rehydrate',
          role: 'user',
          content: 'Question 1',
          status: 'completed',
          parent_user_turn_id: null,
          interrupted_reason: null,
          is_refusal: false,
          fallback_triggered: false,
          trace_id: null,
          node_sequence: [],
          execution_time_ms: 0,
          sources: [],
          sources_consulted: [],
          tool_calls: [],
          memory_proposal: null,
          recalled_memories: [],
          guardrail_interventions: [],
          resolved_country: null,
          created_at: '2026-11-24T21:00:00Z',
          updated_at: '2026-11-24T21:00:00Z',
        },
        {
          turn_id: 'asst_1_interrupted',
          thread_id: 'thr_rehydrate',
          session_id: 'sess_rehydrate',
          role: 'assistant',
          content: 'Partial answer 1...',
          status: 'interrupted',
          parent_user_turn_id: 'usr_1',
          interrupted_reason: 'client_interrupt',
          is_refusal: false,
          fallback_triggered: false,
          trace_id: null,
          node_sequence: [],
          execution_time_ms: 0,
          sources: [],
          sources_consulted: [],
          tool_calls: [],
          memory_proposal: null,
          recalled_memories: [],
          guardrail_interventions: [],
          resolved_country: null,
          created_at: '2026-11-24T21:00:01Z',
          updated_at: '2026-11-24T21:00:02Z',
        },
      ];

      const serverRehydrated: ChatMessageDTO[] = [
        ...existingLocal,
        {
          turn_id: 'usr_2',
          thread_id: 'thr_rehydrate',
          session_id: 'sess_rehydrate',
          role: 'user',
          content: 'Question 2 after redirect',
          status: 'completed',
          parent_user_turn_id: null,
          interrupted_reason: null,
          is_refusal: false,
          fallback_triggered: false,
          trace_id: null,
          node_sequence: [],
          execution_time_ms: 0,
          sources: [],
          sources_consulted: [],
          tool_calls: [],
          memory_proposal: null,
          recalled_memories: [],
          guardrail_interventions: [],
          resolved_country: null,
          created_at: '2026-11-24T21:00:03Z',
          updated_at: '2026-11-24T21:00:03Z',
        },
        {
          turn_id: 'asst_2_completed',
          thread_id: 'thr_rehydrate',
          session_id: 'sess_rehydrate',
          role: 'assistant',
          content: 'Complete grounded answer 2.',
          status: 'completed',
          parent_user_turn_id: 'usr_2',
          interrupted_reason: null,
          is_refusal: false,
          fallback_triggered: false,
          trace_id: 'trace_2',
          node_sequence: ['intake', 'retrieval', 'generation'],
          execution_time_ms: 52.0,
          sources: [],
          sources_consulted: ['rag'],
          tool_calls: [],
          memory_proposal: null,
          recalled_memories: [],
          guardrail_interventions: [],
          resolved_country: 'ES',
          created_at: '2026-11-24T21:00:04Z',
          updated_at: '2026-11-24T21:00:05Z',
        },
      ];

      const merged = mergeRehydratedMessages(existingLocal, serverRehydrated);
      expect(merged).toHaveLength(4);
      expect(merged.map((m) => m.turn_id)).toEqual([
        'usr_1',
        'asst_1_interrupted',
        'usr_2',
        'asst_2_completed',
      ]);
      expect(merged[1]?.status).toBe('interrupted');
      expect(merged[3]?.status).toBe('completed');
    });
  });

  // =========================================================================
  // User Story 5: Strict Domain Alignment & Zero RFP Schema Leakage (T034)
  // =========================================================================
  describe('US5: Strict Support Agent domain field alignment and rejection of RFP SSE schemas', () => {
    it('rejects any frame containing Part 1 RFP SSE fields (rfp_ticket_created, rfp_id, services_requested)', () => {
      const forbiddenRfpEvent = JSON.stringify({
        event: 'rfp_ticket_created',
        thread_id: 'thr_1',
        session_id: 'sess_1',
        ticket_id: 'tkt_0225',
        rfp_id: 'rfp_0071',
        services_requested: ['warehouse'],
        sequence_id: 1,
        timestamp: '2026-11-24T21:00:00Z',
      });
      expect(parseAgentChatStreamEvent(forbiddenRfpEvent)).toBeNull();

      const leakedRfpFieldInTokenChunk = JSON.stringify({
        event: 'token_chunk',
        thread_id: 'thr_1',
        session_id: 'sess_1',
        turn_id: 'turn_1',
        chunk_index: 0,
        delta: 'Hello',
        accumulated_content: 'Hello',
        rfp_id: 'rfp_0071',
        sequence_id: 1,
        timestamp: '2026-11-24T21:00:00Z',
      });
      expect(parseAgentChatStreamEvent(leakedRfpFieldInTokenChunk)).toBeNull();

      const serializedCmd = serializeClientCommand({
        event: 'user_message',
        query: 'Check SLA policy',
        thread_id: 'thr_1',
        session_id: 'sess_1',
        language: 'en',
      });
      expect(JSON.parse(serializedCmd)).toEqual({
        event: 'user_message',
        query: 'Check SLA policy',
        thread_id: 'thr_1',
        session_id: 'sess_1',
        language: 'en',
      });

      const interruptCmd = serializeClientCommand({
        event: 'interrupt_requested',
        turn_id: 'turn_asst_1',
        reason: 'client_interrupt',
      });
      expect(JSON.parse(interruptCmd)).toEqual({
        event: 'interrupt_requested',
        turn_id: 'turn_asst_1',
        reason: 'client_interrupt',
      });

      const snapshotEvent = parseAgentChatStreamEvent(
        JSON.stringify({
          event: 'session_snapshot',
          thread_id: 'thr_1',
          session_id: 'sess_1',
          user_id: 'usr_operator_01',
          agent_id: 'trackflow-support-agent',
          client_id: 'trackflow-backoffice',
          status: 'active',
          session: {
            session_id: 'sess_1',
            thread_id: 'thr_1',
            agent_id: 'trackflow-support-agent',
            client_id: 'trackflow-backoffice',
            user_id: 'usr_operator_01',
            status: 'active',
          },
          messages: [],
          pending_proposal: null,
          latest_checkpoint_id: null,
          checkpoint_count: 0,
          sequence_id: 0,
          timestamp: '2026-11-24T21:00:00Z',
        })
      );
      expect(snapshotEvent).not.toBeNull();
      expect(snapshotEvent?.event).toBe('session_snapshot');
      if (snapshotEvent?.event === 'session_snapshot') {
        expect(snapshotEvent.user_id).toBe('usr_operator_01');
        expect(snapshotEvent.session.agent_id).toBe('trackflow-support-agent');
        expect(snapshotEvent.session.client_id).toBe('trackflow-backoffice');
        expect(snapshotEvent.session.user_id).toBe('usr_operator_01');
        expect(snapshotEvent.session.status).toBe('active');
      }
    });
  });
});
