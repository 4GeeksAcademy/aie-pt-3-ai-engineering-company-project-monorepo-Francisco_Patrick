'use client';

/**
 * React hook managing the Support Agent bidirectional WebSocket connection lifecycle,
 * progressive token-by-token streaming (`token_chunk`), mid-response true generation abort
 * (`interrupt`), mid-stream redirection, progressive exponential backoff reconnection
 * (`1s, 2s, 4s, 8s, 16s, cap 30s`), and thread history rehydration.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  AgentMemoryProposalDTO,
  AgentQueryResponseDTO,
  ChatMessageDTO,
  ChatThreadHistoryResponseDTO,
  WebSocketChatConnectionStatus,
} from '@repo/shared-types';
import { getToken } from '../lib/auth';
import {
  applyStreamEventToMessages,
  buildSupportAgentWebSocketUrl,
  calculateReconnectBackoffMs,
  isPermanentAuthCloseCode,
  mergeRehydratedMessages,
  parseAgentChatStreamEvent,
  serializeClientCommand,
} from '../lib/supportAgentChatClient';

const THREAD_STORAGE_KEY = 'trackflow_support_agent_thread_id';

/**
 * Configuration options for `useSupportAgentChat`.
 */
export interface UseSupportAgentChatOptions {
  /** Base API URL override (defaults to `NEXT_PUBLIC_API_URL` or `http://localhost:8000`). */
  apiUrl?: string;
  /** Optional explicit thread_id override. */
  initialThreadId?: string;
  /** Optional explicit session_id override. */
  initialSessionId?: string;
  /** Preferred response language ('en' or 'es', defaults to 'en'). */
  language?: 'en' | 'es';
  /** Whether to automatically connect the WebSocket on mount (defaults to true). */
  autoConnect?: boolean;
}

/**
 * State and actions exposed by `useSupportAgentChat`.
 */
export interface UseSupportAgentChatResult {
  /** Ordered list of user and assistant turns (`streaming`, `completed`, `interrupted`, `error`). */
  messages: ChatMessageDTO[];
  /** Current WebSocket connection status. */
  connectionStatus: WebSocketChatConnectionStatus;
  /** Bound conversation `thread_id`. */
  threadId: string;
  /** Bound `session_id`. */
  sessionId: string;
  /** True while an assistant response is actively streaming `token_chunk` events. */
  isStreaming: boolean;
  /** Turn ID of the currently streaming assistant message, if any. */
  activeTurnId: string | null;
  /** Active unconfirmed `MemoryProposal` on the thread, if any. */
  pendingProposal: AgentMemoryProposalDTO | null;
  /** Most recent sanitized error message, if any. */
  errorMessage: string | null;
  /** Current reconnection attempt index (`0` when connected). */
  reconnectAttempt: number;
  /** Last monotonic event `sequence_id` received on the thread. */
  lastSequenceId: number;
  /** Submit a new user inquiry (or mid-stream redirecting inquiry) over the WebSocket. */
  sendMessage: (query: string) => Promise<void>;
  /** Immediately interrupt the active streaming assistant response (`{"event": "interrupt"}`). */
  interruptGeneration: () => void;
  /** Manually trigger an immediate WebSocket reconnection and thread rehydration. */
  reconnectNow: () => void;
  /** Start a fresh conversation thread with a new `thread_id`. */
  startNewThread: () => void;
  /** Submit explicit approve/reject feedback on the active `MemoryProposal`. */
  submitProposalFeedback: (action: 'approve' | 'reject') => Promise<void>;
}

function getOrInitializeThreadId(explicitThreadId?: string): string {
  if (explicitThreadId && explicitThreadId.trim().length > 0) {
    return explicitThreadId.trim();
  }
  if (typeof window !== 'undefined') {
    const stored = window.sessionStorage.getItem(THREAD_STORAGE_KEY);
    if (stored && stored.trim().length > 0) {
      return stored.trim();
    }
    const generated = `thr_${Math.random().toString(36).slice(2, 10)}_${Date.now().toString(36)}`;
    window.sessionStorage.setItem(THREAD_STORAGE_KEY, generated);
    return generated;
  }
  return 'thr_default_support';
}

/**
 * Manage bidirectional Support Agent WebSocket streaming chat, true generation abort, and thread rehydration.
 *
 * @param options - Configuration options for API URL, thread binding, and language.
 * @returns Chat timeline state, connection status, and interactive actions.
 */
export function useSupportAgentChat(
  options: UseSupportAgentChatOptions = {}
): UseSupportAgentChatResult {
  const apiUrl =
    options.apiUrl ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
  const language = options.language ?? 'en';
  const autoConnect = options.autoConnect ?? true;

  const [threadId, setThreadId] = useState<string>(() =>
    getOrInitializeThreadId(options.initialThreadId)
  );
  const [sessionId, setSessionId] = useState<string>(() =>
    options.initialSessionId && options.initialSessionId.trim().length > 0
      ? options.initialSessionId.trim()
      : getOrInitializeThreadId(options.initialThreadId)
  );
  const [messages, setMessages] = useState<ChatMessageDTO[]>([]);
  const [connectionStatus, setConnectionStatus] =
    useState<WebSocketChatConnectionStatus>('connecting');
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [pendingProposal, setPendingProposal] =
    useState<AgentMemoryProposalDTO | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState<number>(0);
  const [lastSequenceId, setLastSequenceId] = useState<number>(0);
  const [connectNonce, setConnectNonce] = useState<number>(0);

  const wsRef = useRef<WebSocket | null>(null);
  const activeTurnIdRef = useRef<string | null>(null);
  const isStreamingRef = useRef<boolean>(false);

  const fetchThreadHistoryFallback = useCallback(
    async (targetThreadId: string, token: string): Promise<void> => {
      try {
        const response = await fetch(
          `${apiUrl.replace(/\/$/, '')}/api/v1/agent/threads/${encodeURIComponent(targetThreadId)}/history`,
          {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${token}`,
            },
            cache: 'no-store',
          }
        );
        if (response.status === 401 || response.status === 403) {
          setConnectionStatus('unauthorized');
          return;
        }
        if (!response.ok) {
          return;
        }
        const historyData = (await response.json()) as ChatThreadHistoryResponseDTO;
        if (Array.isArray(historyData.messages)) {
          setMessages((prev) => mergeRehydratedMessages(prev, historyData.messages));
        }
        if (historyData.pending_proposal !== undefined) {
          setPendingProposal(historyData.pending_proposal);
        }
        if (typeof historyData.latest_sequence_id === 'number') {
          setLastSequenceId(historyData.latest_sequence_id);
        }
      } catch {
        // Non-fatal fallback check; WebSocket session_rehydrated will also reconcile
      }
    },
    [apiUrl]
  );

  useEffect(() => {
    if (!autoConnect || typeof window === 'undefined' || typeof WebSocket === 'undefined') {
      return;
    }

    const token = getToken();
    if (!token) {
      setConnectionStatus('unauthorized');
      return;
    }

    let isMounted = true;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let currentAttempt = 0;
    let intentionalClose = false;

    const clearReconnectTimer = (): void => {
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    const connectWebSocket = (): void => {
      if (!isMounted) {
        return;
      }
      const activeToken = getToken();
      if (!activeToken) {
        setConnectionStatus('unauthorized');
        return;
      }

      setConnectionStatus(currentAttempt > 0 ? 'reconnecting' : 'connecting');

      const wsUrl = buildSupportAgentWebSocketUrl({
        apiUrl,
        threadId,
        sessionId,
        token: activeToken,
      });

      let socket: WebSocket;
      try {
        socket = new WebSocket(wsUrl);
      } catch {
        setConnectionStatus('disconnected');
        return;
      }

      wsRef.current = socket;

      socket.onopen = (): void => {
        if (!isMounted) {
          return;
        }
        const wasReconnect = currentAttempt > 0;
        currentAttempt = 0;
        setReconnectAttempt(0);
        setConnectionStatus('connected');
        setErrorMessage(null);
        if (wasReconnect) {
          void fetchThreadHistoryFallback(threadId, activeToken);
        }
      };

      socket.onmessage = (msgEvent: MessageEvent<unknown>): void => {
        if (!isMounted || typeof msgEvent.data !== 'string') {
          return;
        }
        const parsedEvent = parseAgentChatStreamEvent(msgEvent.data);
        if (!parsedEvent) {
          return;
        }

        setLastSequenceId((prev) => Math.max(prev, parsedEvent.sequence_id));
        setMessages((prev) => applyStreamEventToMessages(prev, parsedEvent));

        if (parsedEvent.event === 'session_rehydrated') {
          setPendingProposal(parsedEvent.pending_proposal);
          const streamingTurn = parsedEvent.messages.find(
            (m) => m.role === 'assistant' && m.status === 'streaming'
          );
          if (streamingTurn) {
            isStreamingRef.current = true;
            activeTurnIdRef.current = streamingTurn.turn_id;
            setIsStreaming(true);
            setActiveTurnId(streamingTurn.turn_id);
          } else {
            isStreamingRef.current = false;
            activeTurnIdRef.current = null;
            setIsStreaming(false);
            setActiveTurnId(null);
          }
        } else if (parsedEvent.event === 'generation_started') {
          isStreamingRef.current = true;
          activeTurnIdRef.current = parsedEvent.turn_id;
          setIsStreaming(true);
          setActiveTurnId(parsedEvent.turn_id);
          setErrorMessage(null);
        } else if (parsedEvent.event === 'token_chunk') {
          isStreamingRef.current = true;
          activeTurnIdRef.current = parsedEvent.turn_id;
          setIsStreaming(true);
          setActiveTurnId(parsedEvent.turn_id);
        } else if (parsedEvent.event === 'generation_interrupted') {
          if (
            activeTurnIdRef.current === null ||
            activeTurnIdRef.current === parsedEvent.turn_id
          ) {
            isStreamingRef.current = false;
            activeTurnIdRef.current = null;
            setIsStreaming(false);
            setActiveTurnId(null);
          }
        } else if (parsedEvent.event === 'generation_completed') {
          isStreamingRef.current = false;
          activeTurnIdRef.current = null;
          setIsStreaming(false);
          setActiveTurnId(null);
          setPendingProposal(parsedEvent.memory_proposal);
        } else if (parsedEvent.event === 'error') {
          isStreamingRef.current = false;
          activeTurnIdRef.current = null;
          setIsStreaming(false);
          setActiveTurnId(null);
          setErrorMessage(parsedEvent.detail);
        }
      };

      socket.onclose = (closeEvent: CloseEvent): void => {
        if (!isMounted || intentionalClose) {
          return;
        }
        wsRef.current = null;

        if (isPermanentAuthCloseCode(closeEvent.code)) {
          isStreamingRef.current = false;
          activeTurnIdRef.current = null;
          setIsStreaming(false);
          setActiveTurnId(null);
          setConnectionStatus('unauthorized');
          setReconnectAttempt(0);
          setErrorMessage(
            closeEvent.code === 4003
              ? 'This conversation thread belongs to another operator account (4003).'
              : 'WebSocket authentication failed or session token expired (4001).'
          );
          return;
        }

        const delayMs = calculateReconnectBackoffMs(currentAttempt);
        currentAttempt += 1;
        setReconnectAttempt(currentAttempt);
        setConnectionStatus('reconnecting');
        clearReconnectTimer();
        reconnectTimer = setTimeout(() => {
          connectWebSocket();
        }, delayMs);
      };
    };

    connectWebSocket();

    return () => {
      isMounted = false;
      intentionalClose = true;
      clearReconnectTimer();
      if (wsRef.current) {
        try {
          wsRef.current.close(1000, 'Component unmounted');
        } catch {
          // Ignore close errors on unmount
        }
        wsRef.current = null;
      }
      setConnectionStatus('disconnected');
    };
  }, [apiUrl, autoConnect, connectNonce, fetchThreadHistoryFallback, sessionId, threadId]);

  const interruptGeneration = useCallback((): void => {
    const socket = wsRef.current;
    const currentTurnId = activeTurnIdRef.current;

    // Optimistically mark the active streaming bubble as interrupted so partial text is immediately preserved in the UI
    if (currentTurnId) {
      const nowIso = new Date().toISOString();
      setMessages((prev) =>
        prev.map((m) =>
          m.turn_id === currentTurnId && m.status === 'streaming'
            ? {
                ...m,
                status: 'interrupted',
                interrupted_reason: 'client_interrupt',
                updated_at: nowIso,
              }
            : m
        )
      );
    }

    isStreamingRef.current = false;
    activeTurnIdRef.current = null;
    setIsStreaming(false);
    setActiveTurnId(null);

    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(
        serializeClientCommand({
          event: 'interrupt',
          turn_id: currentTurnId,
          reason: 'client_interrupt',
        })
      );
    }
  }, []);

  const sendMessage = useCallback(
    async (rawQuery: string): Promise<void> => {
      const trimmed = rawQuery.trim();
      if (!trimmed) {
        return;
      }
      setErrorMessage(null);
      const nowIso = new Date().toISOString();
      const userTurnId = `usr_${Math.random().toString(36).slice(2, 10)}_${Date.now().toString(36)}`;

      // If currently streaming, preserve the partial response with status="interrupted" before redirecting (FR-009, FR-010)
      const currentStreamingTurnId = activeTurnIdRef.current;
      setMessages((prev) => {
        const updated = prev.map((m) =>
          (currentStreamingTurnId && m.turn_id === currentStreamingTurnId && m.status === 'streaming') ||
          m.status === 'streaming'
            ? {
                ...m,
                status: 'interrupted' as const,
                interrupted_reason: 'redirect_new_message' as const,
                updated_at: nowIso,
              }
            : m
        );
        return [
          ...updated,
          {
            turn_id: userTurnId,
            thread_id: threadId,
            session_id: sessionId,
            role: 'user',
            content: trimmed,
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
            created_at: nowIso,
            updated_at: nowIso,
          },
        ];
      });

      const socket = wsRef.current;
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(
          serializeClientCommand({
            event: 'user_message',
            query: trimmed,
            turn_id: userTurnId,
            thread_id: threadId,
            session_id: sessionId,
            language,
            top_k: 3,
            min_score: 0.62,
          })
        );
        return;
      }

      // Synchronous REST fallback (`POST /api/v1/agent/query`) when WebSocket is disconnected
      const fallbackAssistantTurnId = `turn_${Math.random().toString(36).slice(2, 10)}`;
      isStreamingRef.current = true;
      activeTurnIdRef.current = fallbackAssistantTurnId;
      setIsStreaming(true);
      setActiveTurnId(fallbackAssistantTurnId);

      try {
        const token = getToken();
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
        };
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(`${apiUrl.replace(/\/$/, '')}/api/v1/agent/query`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            query: trimmed,
            thread_id: threadId,
            language,
            top_k: 3,
            min_score: 0.62,
          }),
        });
        if (!response.ok) {
          throw new Error(`Support Agent service returned HTTP ${response.status}`);
        }
        const result = (await response.json()) as AgentQueryResponseDTO;
        const doneIso = new Date().toISOString();
        setMessages((prev) => [
          ...prev,
          {
            turn_id: fallbackAssistantTurnId,
            thread_id: threadId,
            session_id: sessionId,
            role: 'assistant',
            content: result.answer,
            status: 'completed',
            parent_user_turn_id: userTurnId,
            interrupted_reason: null,
            is_refusal: result.is_refusal,
            fallback_triggered: result.fallback_triggered,
            trace_id: result.trace_id,
            node_sequence: result.node_sequence ?? [],
            execution_time_ms: result.execution_time_ms ?? 0,
            sources: result.sources ?? [],
            sources_consulted: result.sources_consulted ?? [],
            tool_calls: result.tool_calls ?? [],
            memory_proposal: result.memory_proposal ?? null,
            recalled_memories: result.recalled_memories ?? [],
            guardrail_interventions: result.guardrail_interventions ?? [],
            resolved_country: result.resolved_country ?? null,
            created_at: doneIso,
            updated_at: doneIso,
          },
        ]);
        if (result.memory_proposal) {
          setPendingProposal(result.memory_proposal);
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error
            ? err.message
            : 'Unable to reach the TrackFlow Support Agent service.';
        setErrorMessage(message);
      } finally {
        isStreamingRef.current = false;
        activeTurnIdRef.current = null;
        setIsStreaming(false);
        setActiveTurnId(null);
      }
    },
    [apiUrl, language, sessionId, threadId]
  );

  const reconnectNow = useCallback((): void => {
    setReconnectAttempt(0);
    setErrorMessage(null);
    setConnectionStatus('connecting');
    setConnectNonce((n) => n + 1);
  }, []);

  const startNewThread = useCallback((): void => {
    const newThread = `thr_${Math.random().toString(36).slice(2, 10)}_${Date.now().toString(36)}`;
    if (typeof window !== 'undefined') {
      window.sessionStorage.setItem(THREAD_STORAGE_KEY, newThread);
    }
    isStreamingRef.current = false;
    activeTurnIdRef.current = null;
    setIsStreaming(false);
    setActiveTurnId(null);
    setMessages([]);
    setPendingProposal(null);
    setErrorMessage(null);
    setThreadId(newThread);
    setSessionId(newThread);
    setConnectNonce((n) => n + 1);
  }, []);

  const submitProposalFeedback = useCallback(
    async (action: 'approve' | 'reject'): Promise<void> => {
      if (!pendingProposal) {
        return;
      }
      try {
        const token = getToken();
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
        };
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(
          `${apiUrl.replace(/\/$/, '')}/api/v1/agent/proposals/${encodeURIComponent(pendingProposal.proposal_id)}/feedback`,
          {
            method: 'POST',
            headers,
            body: JSON.stringify({ action }),
          }
        );
        if (response.ok) {
          setPendingProposal(null);
        }
      } catch {
        // Non-fatal; operator can also confirm or reject conversationally in the next turn
      }
    },
    [apiUrl, pendingProposal]
  );

  return {
    messages,
    connectionStatus,
    threadId,
    sessionId,
    isStreaming,
    activeTurnId,
    pendingProposal,
    errorMessage,
    reconnectAttempt,
    lastSequenceId,
    sendMessage,
    interruptGeneration,
    reconnectNow,
    startNewThread,
    submitProposalFeedback,
  };
}
