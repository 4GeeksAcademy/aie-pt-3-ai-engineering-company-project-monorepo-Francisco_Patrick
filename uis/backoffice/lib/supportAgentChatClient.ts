/**
 * Typed WebSocket frame parser, client command serializer, progressive exponential backoff calculator,
 * live token chunk reducer, and turn history deduplication utilities for the TrackFlow Support Agent
 * Real-Time Bidirectional WebSocket Streaming Chat (Part 2).
 */

import type {
  AgentChatClientCommandDTO,
  AgentChatStreamEventDTO,
  AgentGuardrailInterventionDTO,
  AgentMemoryProposalDTO,
  AgentOperatingCountry,
  AgentToolCallTraceDTO,
  ChatInterruptedReason,
  ChatMessageDTO,
  ChatSessionDTO,
  ChatSessionStatus,
  ChatTurnRole,
  ChatTurnStatus,
  KnowledgeSourceCitationDTO,
  ServerErrorEventDTO,
  ServerGenerationCompletedEventDTO,
  ServerGenerationInterruptedEventDTO,
  ServerGenerationStartedEventDTO,
  ServerPongEventDTO,
  ServerSessionSnapshotEventDTO,
  ServerTokenChunkEventDTO,
} from '@repo/shared-types';

const VALID_ROLES: ReadonlySet<ChatTurnRole> = new Set<ChatTurnRole>(['user', 'assistant']);
const VALID_STATUSES: ReadonlySet<ChatTurnStatus> = new Set<ChatTurnStatus>([
  'streaming',
  'completed',
  'interrupted',
  'error',
]);
const VALID_SESSION_STATUSES: ReadonlySet<ChatSessionStatus> =
  new Set<ChatSessionStatus>(['active', 'interrupted', 'closed']);
const LEGACY_SESSION_STATUS_MAP: Readonly<Record<string, ChatSessionStatus>> = {
  streaming: 'active',
  disconnected: 'interrupted',
};
const FIRST_LINE_AGENT_ID = 'first_line_cx';
const UNASSIGNED_CLIENT_USER_ID = 'unassigned';
const LEGACY_AGENT_IDS: ReadonlySet<string> = new Set<string>([
  'trackflow-support-agent',
]);

/**
 * Normalizes a raw session status into the briefing enum `active | interrupted | closed`.
 *
 * @param candidate - Raw status string from the wire (may be a legacy value).
 * @returns A compliant status; unknown values fall back to `active`.
 */
export function normalizeSessionStatus(candidate: string): ChatSessionStatus {
  if (VALID_SESSION_STATUSES.has(candidate as ChatSessionStatus)) {
    return candidate as ChatSessionStatus;
  }
  return LEGACY_SESSION_STATUS_MAP[candidate] ?? 'active';
}

/**
 * Normalizes a raw agent id, mapping empty/legacy values to `first_line_cx`.
 *
 * @param candidate - Raw agent id from the wire.
 * @returns The briefing agent id or the supplied custom id.
 */
export function normalizeAgentId(candidate: string): string {
  return candidate.length === 0 || LEGACY_AGENT_IDS.has(candidate)
    ? FIRST_LINE_AGENT_ID
    : candidate;
}
const VALID_INTERRUPTED_REASONS: ReadonlySet<ChatInterruptedReason> =
  new Set<ChatInterruptedReason>([
    'client_interrupt',
    'redirect_new_message',
    'client_disconnect',
  ]);
const PROHIBITED_RFP_FIELDS: readonly string[] = [
  'rfp_ticket_created',
  'rfp_id',
  'services_requested',
];

/**
 * Custom error representing a WebSocket authentication (`4001`) or thread ownership (`4003`) rejection.
 */
export class WebSocketChatAuthError extends Error {
  /** WebSocket close code or HTTP status code (`4001`, `4003`, `401`, or `403`). */
  public readonly closeCode: number;

  /**
   * Create a new WebSocketChatAuthError.
   *
   * @param closeCode - Close code or HTTP status code (4001, 4003, 401, 403).
   * @param message - Human-readable rejection message.
   */
  public constructor(closeCode: number, message: string) {
    super(message);
    this.name = 'WebSocketChatAuthError';
    this.closeCode = closeCode;
  }
}

/**
 * Calculate progressive exponential backoff delay in milliseconds for WebSocket reconnection attempts.
 *
 * Follows the exact schedule `1s, 2s, 4s, 8s, 16s`, capped at `30s` (`30,000` ms) per FR-011.
 *
 * @param attempt - Zero-based reconnection attempt index (`0` -> 1000ms, `1` -> 2000ms, etc.).
 * @returns Backoff delay in milliseconds in `[1000, 30000]`.
 */
export function calculateReconnectBackoffMs(attempt: number): number {
  const safeAttempt = Math.max(0, Math.floor(attempt));
  const delay = 1000 * Math.pow(2, safeAttempt);
  return Math.min(delay, 30000);
}

/**
 * Determine whether a WebSocket close code represents a permanent authentication or ownership rejection
 * that MUST halt automatic reconnection attempts immediately (FR-002, FR-003, FR-011).
 *
 * @param closeCode - Numeric WebSocket close code.
 * @returns True if closeCode is `4001`, `4003`, or policy violation `1008`.
 */
export function isPermanentAuthCloseCode(closeCode: number): boolean {
  return closeCode === 4001 || closeCode === 4003 || closeCode === 1008;
}

/**
 * Build the WebSocket connection URL (`/api/v1/agent/ws`) from an HTTP/HTTPS API base URL,
 * attaching `thread_id`, `session_id`, and optional `token` query parameters.
 *
 * @param params - API base URL, thread_id, session_id, and optional JWT token.
 * @returns Full `ws://` or `wss://` endpoint URL string.
 */
export function buildSupportAgentWebSocketUrl(params: {
  apiUrl: string;
  threadId: string;
  sessionId: string;
  token?: string | null | undefined;
}): string {
  const normalizedBase = params.apiUrl.trim().replace(/\/$/, '');
  const wsBase = normalizedBase
    .replace(/^https:\/\//i, 'wss://')
    .replace(/^http:\/\//i, 'ws://');
  const searchParams = new URLSearchParams();
  searchParams.set('thread_id', params.threadId);
  searchParams.set('session_id', params.sessionId);
  if (params.token && params.token.trim().length > 0) {
    searchParams.set('token', params.token.trim());
  }
  return `${wsBase}/api/v1/agent/ws?${searchParams.toString()}`;
}

/**
 * Serialize a typed client-to-server command into a JSON WebSocket frame string.
 *
 * @param command - Discriminated `AgentChatClientCommandDTO` object.
 * @returns JSON string ready for `websocket.send()`.
 */
export function serializeClientCommand(command: AgentChatClientCommandDTO): string {
  return JSON.stringify(command);
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasProhibitedRFPFields(record: Record<string, unknown>): boolean {
  for (const field of PROHIBITED_RFP_FIELDS) {
    if (field in record) {
      return true;
    }
  }
  if (typeof record['event'] === 'string' && record['event'] === 'rfp_ticket_created') {
    return true;
  }
  return false;
}

function parseSourceCitations(raw: unknown): KnowledgeSourceCitationDTO[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const result: KnowledgeSourceCitationDTO[] = [];
  for (const item of raw) {
    if (!isPlainRecord(item)) {
      continue;
    }
    const doc = typeof item['source_document'] === 'string' ? item['source_document'] : '';
    const section = typeof item['section'] === 'string' ? item['section'] : '';
    const score =
      typeof item['similarity_score'] === 'number' ? item['similarity_score'] : 0;
    if (doc && section) {
      result.push({
        source_document: doc,
        section,
        similarity_score: score,
      });
    }
  }
  return result;
}

function parseToolCalls(raw: unknown): AgentToolCallTraceDTO[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const result: AgentToolCallTraceDTO[] = [];
  for (const item of raw) {
    if (!isPlainRecord(item)) {
      continue;
    }
    const toolName = item['tool_name'];
    const status = item['status'];
    if (
      (toolName === 'ticket_tool' || toolName === 'inventory_tool') &&
      (status === 'success' ||
        status === 'not_found' ||
        status === 'timeout' ||
        status === 'error')
    ) {
      result.push({
        tool_name: toolName,
        status,
        total_matched:
          typeof item['total_matched'] === 'number' ? item['total_matched'] : 0,
        returned_count:
          typeof item['returned_count'] === 'number' ? item['returned_count'] : 0,
        latency_ms: typeof item['latency_ms'] === 'number' ? item['latency_ms'] : 0,
        error_message:
          typeof item['error_message'] === 'string' ? item['error_message'] : null,
      });
    }
  }
  return result;
}

function parseMemoryProposal(raw: unknown): AgentMemoryProposalDTO | null {
  if (!isPlainRecord(raw)) {
    return null;
  }
  const proposalId =
    typeof raw['proposal_id'] === 'string' ? raw['proposal_id'].trim() : '';
  const category = raw['category'];
  const targetEntity =
    typeof raw['target_entity'] === 'string' ? raw['target_entity'] : '';
  const summary = typeof raw['summary'] === 'string' ? raw['summary'] : '';
  const status = raw['status'];
  if (
    !proposalId ||
    !targetEntity ||
    !summary ||
    (category !== 'carrier_rule' &&
      category !== 'incident_context' &&
      category !== 'b2b_preference') ||
    (status !== 'pending' &&
      status !== 'approved' &&
      status !== 'rejected' &&
      status !== 'edited' &&
      status !== 'discarded')
  ) {
    return null;
  }
  return {
    proposal_id: proposalId,
    category,
    target_entity: targetEntity,
    country_code: typeof raw['country_code'] === 'string' ? raw['country_code'] : null,
    summary,
    status,
    confidence: typeof raw['confidence'] === 'number' ? raw['confidence'] : 0.9,
    created_at:
      typeof raw['created_at'] === 'string'
        ? raw['created_at']
        : new Date().toISOString(),
  };
}

function parseGuardrailInterventions(raw: unknown): AgentGuardrailInterventionDTO[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const result: AgentGuardrailInterventionDTO[] = [];
  for (const item of raw) {
    if (!isPlainRecord(item)) {
      continue;
    }
    const eventId = typeof item['event_id'] === 'string' ? item['event_id'] : '';
    const failureType = item['failure_type'];
    const layer = item['layer'];
    const disposition = item['disposition'];
    if (
      eventId &&
      (failureType === 'structural' ||
        failureType === 'content' ||
        failureType === 'security') &&
      (layer === 'input_guard' ||
        layer === 'authorization_guard' ||
        layer === 'context_sanitizer' ||
        layer === 'output_guard') &&
      (disposition === 'blocked' ||
        disposition === 'redirected' ||
        disposition === 'deflected' ||
        disposition === 'clarified')
    ) {
      result.push({
        event_id: eventId,
        timestamp:
          typeof item['timestamp'] === 'string'
            ? item['timestamp']
            : new Date().toISOString(),
        session_id: typeof item['session_id'] === 'string' ? item['session_id'] : '',
        trace_id: typeof item['trace_id'] === 'string' ? item['trace_id'] : null,
        failure_type: failureType,
        layer,
        input_category:
          typeof item['input_category'] === 'string'
            ? item['input_category']
            : 'out_of_domain',
        reason_code: typeof item['reason_code'] === 'string' ? item['reason_code'] : '',
        disposition,
        redacted_preview:
          typeof item['redacted_preview'] === 'string' ? item['redacted_preview'] : '',
      });
    }
  }
  return result;
}

/**
 * Parse and validate a raw ChatMessage dictionary object.
 *
 * @param raw - Unknown object from a rehydration or REST history payload.
 * @returns Validated `ChatMessageDTO` or `null` if invalid.
 */
export function parseChatMessageRecord(raw: unknown): ChatMessageDTO | null {
  if (!isPlainRecord(raw) || hasProhibitedRFPFields(raw)) {
    return null;
  }
  const turnId = typeof raw['turn_id'] === 'string' ? raw['turn_id'].trim() : '';
  const threadId = typeof raw['thread_id'] === 'string' ? raw['thread_id'].trim() : '';
  const sessionId =
    typeof raw['session_id'] === 'string' && raw['session_id'].trim().length > 0
      ? raw['session_id'].trim()
      : threadId;
  const role = raw['role'];
  const status = raw['status'];
  const content = typeof raw['content'] === 'string' ? raw['content'] : '';

  if (
    !turnId ||
    !threadId ||
    typeof role !== 'string' ||
    !VALID_ROLES.has(role as ChatTurnRole) ||
    typeof status !== 'string' ||
    !VALID_STATUSES.has(status as ChatTurnStatus)
  ) {
    return null;
  }

  const interruptedReasonRaw = raw['interrupted_reason'];
  const interruptedReason: ChatInterruptedReason | null =
    typeof interruptedReasonRaw === 'string' &&
    VALID_INTERRUPTED_REASONS.has(interruptedReasonRaw as ChatInterruptedReason)
      ? (interruptedReasonRaw as ChatInterruptedReason)
      : null;

  const resolvedCountryRaw = raw['resolved_country'];
  const resolvedCountry: AgentOperatingCountry | null =
    resolvedCountryRaw === 'US' || resolvedCountryRaw === 'ES'
      ? resolvedCountryRaw
      : null;

  const nowIso = new Date().toISOString();

  return {
    turn_id: turnId,
    thread_id: threadId,
    session_id: sessionId,
    role: role as ChatTurnRole,
    content,
    status: status as ChatTurnStatus,
    parent_user_turn_id:
      typeof raw['parent_user_turn_id'] === 'string' ? raw['parent_user_turn_id'] : null,
    interrupted_reason: interruptedReason,
    is_refusal: Boolean(raw['is_refusal']),
    fallback_triggered: Boolean(raw['fallback_triggered']),
    trace_id: typeof raw['trace_id'] === 'string' ? raw['trace_id'] : null,
    node_sequence: Array.isArray(raw['node_sequence'])
      ? raw['node_sequence'].filter((n): n is string => typeof n === 'string')
      : [],
    execution_time_ms:
      typeof raw['execution_time_ms'] === 'number' ? raw['execution_time_ms'] : 0,
    sources: parseSourceCitations(raw['sources']),
    sources_consulted: Array.isArray(raw['sources_consulted'])
      ? raw['sources_consulted'].filter((s): s is string => typeof s === 'string')
      : [],
    tool_calls: parseToolCalls(raw['tool_calls']),
    memory_proposal: parseMemoryProposal(raw['memory_proposal']),
    recalled_memories: Array.isArray(raw['recalled_memories'])
      ? raw['recalled_memories'].filter((m): m is string => typeof m === 'string')
      : [],
    guardrail_interventions: parseGuardrailInterventions(raw['guardrail_interventions']),
    resolved_country: resolvedCountry,
    created_at: typeof raw['created_at'] === 'string' ? raw['created_at'] : nowIso,
    updated_at: typeof raw['updated_at'] === 'string' ? raw['updated_at'] : nowIso,
  };
}

/**
 * Parse and validate an incoming raw WebSocket text frame into a discriminated `AgentChatStreamEventDTO`.
 *
 * Strictly enforces TrackFlow Support Agent domain field conventions and rejects unknown events
 * or any payload leaking Part 1's RFP Ticket SSE schema (`rfp_ticket_created`, `rfp_id`, `services_requested`).
 *
 * @param rawJson - Raw JSON text frame received from `/api/v1/agent/ws`.
 * @returns Validated `AgentChatStreamEventDTO` or `null` if malformed/invalid.
 */
export function parseAgentChatStreamEvent(
  rawJson: string
): AgentChatStreamEventDTO | null {
  try {
    const parsed: unknown = JSON.parse(rawJson);
    if (!isPlainRecord(parsed) || hasProhibitedRFPFields(parsed)) {
      return null;
    }

    const eventType = parsed['event'];
    const threadId =
      typeof parsed['thread_id'] === 'string' ? parsed['thread_id'].trim() : '';
    const sessionId =
      typeof parsed['session_id'] === 'string' && parsed['session_id'].trim().length > 0
        ? parsed['session_id'].trim()
        : threadId;
    const sequenceId =
      typeof parsed['sequence_id'] === 'number' ? parsed['sequence_id'] : -1;
    const timestamp =
      typeof parsed['timestamp'] === 'string' ? parsed['timestamp'].trim() : '';

    if (!threadId || !sessionId || sequenceId < 0 || !timestamp) {
      return null;
    }

    if (eventType === 'session_snapshot' || eventType === 'session_rehydrated') {
      const rawSession = isPlainRecord(parsed['session']) ? parsed['session'] : null;
      const userId =
        rawSession &&
        typeof rawSession['user_id'] === 'string' &&
        rawSession['user_id'].trim().length > 0
          ? rawSession['user_id'].trim()
          : typeof parsed['user_id'] === 'string' &&
              parsed['user_id'].trim().length > 0
            ? parsed['user_id'].trim()
            : UNASSIGNED_CLIENT_USER_ID;
      const rawAgentCandidate =
        typeof parsed['agent_id'] === 'string' && parsed['agent_id'].trim().length > 0
          ? parsed['agent_id'].trim()
          : rawSession && typeof rawSession['agent_id'] === 'string'
            ? rawSession['agent_id'].trim()
            : '';
      const agentId = normalizeAgentId(rawAgentCandidate);
      const clientId =
        typeof parsed['client_id'] === 'string' && parsed['client_id'].length > 0
          ? parsed['client_id']
          : rawSession && typeof rawSession['client_id'] === 'string'
            ? rawSession['client_id']
            : 'trackflow-backoffice';
      const statusCandidate =
        typeof parsed['status'] === 'string'
          ? parsed['status']
          : rawSession && typeof rawSession['status'] === 'string'
            ? rawSession['status']
            : 'active';
      const sessionStatus: ChatSessionStatus =
        normalizeSessionStatus(statusCandidate);
      const sessionObj: ChatSessionDTO = {
        session_id:
          rawSession && typeof rawSession['session_id'] === 'string'
            ? rawSession['session_id']
            : sessionId,
        thread_id:
          rawSession && typeof rawSession['thread_id'] === 'string'
            ? rawSession['thread_id']
            : threadId,
        agent_id: agentId,
        client_id: clientId,
        user_id: userId,
        status: sessionStatus,
        created_at:
          rawSession && typeof rawSession['created_at'] === 'string'
            ? rawSession['created_at']
            : timestamp,
        updated_at:
          rawSession && typeof rawSession['updated_at'] === 'string'
            ? rawSession['updated_at']
            : timestamp,
      };
      const rawMessages = Array.isArray(parsed['messages']) ? parsed['messages'] : [];
      const messages: ChatMessageDTO[] = [];
      for (const item of rawMessages) {
        const msg = parseChatMessageRecord(item);
        if (msg) {
          messages.push(msg);
        }
      }
      const ev: ServerSessionSnapshotEventDTO = {
        event: 'session_snapshot',
        thread_id: threadId,
        session_id: sessionId,
        user_id: userId,
        agent_id: agentId,
        client_id: clientId,
        status: sessionStatus,
        session: sessionObj,
        messages,
        pending_proposal: parseMemoryProposal(parsed['pending_proposal']),
        latest_checkpoint_id:
          typeof parsed['latest_checkpoint_id'] === 'string'
            ? parsed['latest_checkpoint_id']
            : null,
        checkpoint_count:
          typeof parsed['checkpoint_count'] === 'number' ? parsed['checkpoint_count'] : 0,
        sequence_id: sequenceId,
        timestamp,
      };
      return ev;
    }

    if (eventType === 'generation_started') {
      const turnId =
        typeof parsed['turn_id'] === 'string' ? parsed['turn_id'].trim() : '';
      const userTurnId =
        typeof parsed['user_turn_id'] === 'string' ? parsed['user_turn_id'].trim() : '';
      const query = typeof parsed['query'] === 'string' ? parsed['query'] : '';
      if (!turnId || !userTurnId) {
        return null;
      }
      const ev: ServerGenerationStartedEventDTO = {
        event: 'generation_started',
        thread_id: threadId,
        session_id: sessionId,
        turn_id: turnId,
        user_turn_id: userTurnId,
        query,
        sequence_id: sequenceId,
        timestamp,
      };
      return ev;
    }

    if (eventType === 'token_chunk') {
      const turnId =
        typeof parsed['turn_id'] === 'string' ? parsed['turn_id'].trim() : '';
      const chunkIndex =
        typeof parsed['chunk_index'] === 'number' ? parsed['chunk_index'] : -1;
      const delta = typeof parsed['delta'] === 'string' ? parsed['delta'] : null;
      const accumulatedContent =
        typeof parsed['accumulated_content'] === 'string'
          ? parsed['accumulated_content']
          : null;
      if (!turnId || chunkIndex < 0 || delta === null || accumulatedContent === null) {
        return null;
      }
      const ev: ServerTokenChunkEventDTO = {
        event: 'token_chunk',
        thread_id: threadId,
        session_id: sessionId,
        turn_id: turnId,
        chunk_index: chunkIndex,
        delta,
        accumulated_content: accumulatedContent,
        sequence_id: sequenceId,
        timestamp,
      };
      return ev;
    }

    if (eventType === 'generation_interrupted') {
      const turnId =
        typeof parsed['turn_id'] === 'string' ? parsed['turn_id'].trim() : '';
      const partialContent =
        typeof parsed['partial_content'] === 'string' ? parsed['partial_content'] : null;
      const reasonRaw = parsed['reason'];
      if (
        !turnId ||
        partialContent === null ||
        typeof reasonRaw !== 'string' ||
        !VALID_INTERRUPTED_REASONS.has(reasonRaw as ChatInterruptedReason)
      ) {
        return null;
      }
      const ev: ServerGenerationInterruptedEventDTO = {
        event: 'generation_interrupted',
        thread_id: threadId,
        session_id: sessionId,
        turn_id: turnId,
        partial_content: partialContent,
        status: 'interrupted',
        reason: reasonRaw as ChatInterruptedReason,
        sequence_id: sequenceId,
        timestamp,
      };
      return ev;
    }

    if (eventType === 'generation_completed') {
      const turnId =
        typeof parsed['turn_id'] === 'string' ? parsed['turn_id'].trim() : '';
      const query = typeof parsed['query'] === 'string' ? parsed['query'] : '';
      const content = typeof parsed['content'] === 'string' ? parsed['content'] : null;
      const traceId = typeof parsed['trace_id'] === 'string' ? parsed['trace_id'] : '';
      if (!turnId || content === null || !traceId) {
        return null;
      }
      const resolvedCountryRaw = parsed['resolved_country'];
      const resolvedCountry: AgentOperatingCountry | null =
        resolvedCountryRaw === 'US' || resolvedCountryRaw === 'ES'
          ? resolvedCountryRaw
          : null;
      const ev: ServerGenerationCompletedEventDTO = {
        event: 'generation_completed',
        thread_id: threadId,
        session_id: sessionId,
        turn_id: turnId,
        query,
        content,
        status: 'completed',
        is_refusal: Boolean(parsed['is_refusal']),
        fallback_triggered: Boolean(parsed['fallback_triggered']),
        trace_id: traceId,
        node_sequence: Array.isArray(parsed['node_sequence'])
          ? parsed['node_sequence'].filter((n): n is string => typeof n === 'string')
          : [],
        execution_time_ms:
          typeof parsed['execution_time_ms'] === 'number'
            ? parsed['execution_time_ms']
            : 0,
        sources: parseSourceCitations(parsed['sources']),
        sources_consulted: Array.isArray(parsed['sources_consulted'])
          ? parsed['sources_consulted'].filter((s): s is string => typeof s === 'string')
          : [],
        tool_calls: parseToolCalls(parsed['tool_calls']),
        memory_proposal: parseMemoryProposal(parsed['memory_proposal']),
        recalled_memories: Array.isArray(parsed['recalled_memories'])
          ? parsed['recalled_memories'].filter((m): m is string => typeof m === 'string')
          : [],
        guardrail_interventions: parseGuardrailInterventions(
          parsed['guardrail_interventions']
        ),
        resolved_country: resolvedCountry,
        sequence_id: sequenceId,
        timestamp,
      };
      return ev;
    }

    if (eventType === 'error') {
      const errorCode =
        typeof parsed['error_code'] === 'string' ? parsed['error_code'] : '';
      const detail = typeof parsed['detail'] === 'string' ? parsed['detail'] : '';
      if (!errorCode || !detail) {
        return null;
      }
      const ev: ServerErrorEventDTO = {
        event: 'error',
        thread_id: threadId,
        session_id: sessionId,
        turn_id: typeof parsed['turn_id'] === 'string' ? parsed['turn_id'] : null,
        error_code: errorCode,
        detail,
        sequence_id: sequenceId,
        timestamp,
      };
      return ev;
    }

    if (eventType === 'pong') {
      const ev: ServerPongEventDTO = {
        event: 'pong',
        thread_id: threadId,
        session_id: sessionId,
        sequence_id: sequenceId,
        timestamp,
      };
      return ev;
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Merge and deduplicate existing client messages with rehydrated server history by `turn_id`.
 *
 * Preserves chronological turn order while guaranteeing zero duplicate bubbles across
 * WebSocket reconnects or REST history reconciliation (FR-011, FR-012, SC-005).
 *
 * @param existingMessages - Current message list in UI state.
 * @param rehydratedMessages - Incoming rehydrated message list from `session_rehydrated` or REST history.
 * @returns Deduplicated, chronologically ordered array of `ChatMessageDTO`.
 */
export function mergeRehydratedMessages(
  existingMessages: readonly ChatMessageDTO[],
  rehydratedMessages: readonly ChatMessageDTO[]
): ChatMessageDTO[] {
  const byTurnId = new Map<string, ChatMessageDTO>();
  const order: string[] = [];

  for (const msg of rehydratedMessages) {
    if (!byTurnId.has(msg.turn_id)) {
      order.push(msg.turn_id);
    }
    byTurnId.set(msg.turn_id, { ...msg });
  }

  for (const localMsg of existingMessages) {
    const serverVersion = byTurnId.get(localMsg.turn_id);
    if (!serverVersion) {
      order.push(localMsg.turn_id);
      byTurnId.set(localMsg.turn_id, { ...localMsg });
    } else if (
      serverVersion.status === 'streaming' &&
      localMsg.content.length > serverVersion.content.length
    ) {
      byTurnId.set(localMsg.turn_id, {
        ...serverVersion,
        content: localMsg.content,
      });
    }
  }

  return order
    .map((id) => byTurnId.get(id))
    .filter((item): item is ChatMessageDTO => item !== undefined);
}

/**
 * Pure reducer applying a single `AgentChatStreamEventDTO` frame to the conversation message timeline.
 *
 * Handles:
 * - `session_rehydrated`: merges and deduplicates all persisted turns by `turn_id`.
 * - `generation_started`: ensures the user turn exists and creates/initializes the `streaming` assistant bubble.
 * - `token_chunk`: progressively appends/updates the active assistant bubble's content in real time.
 * - `generation_interrupted`: permanently marks the active assistant turn as `status: "interrupted"` while preserving all partial content rendered so far.
 * - `generation_completed`: transitions the active assistant turn to `status: "completed"` with full grounded citations, consulted sources, tool calls, memory proposals, and guardrail decisions.
 *
 * @param currentMessages - Existing array of `ChatMessageDTO` in UI state.
 * @param event - Incoming validated `AgentChatStreamEventDTO`.
 * @returns Updated array of `ChatMessageDTO`.
 */
export function applyStreamEventToMessages(
  currentMessages: readonly ChatMessageDTO[],
  event: AgentChatStreamEventDTO
): ChatMessageDTO[] {
  if (event.event === 'session_snapshot') {
    return mergeRehydratedMessages(currentMessages, event.messages);
  }

  if (event.event === 'generation_started') {
    const next = [...currentMessages];
    const hasUserTurn = next.some(
      (m) =>
        m.turn_id === event.user_turn_id ||
        (m.role === 'user' && m.content.trim() === event.query.trim())
    );
    if (!hasUserTurn && event.query.trim().length > 0) {
      next.push({
        turn_id: event.user_turn_id,
        thread_id: event.thread_id,
        session_id: event.session_id,
        role: 'user',
        content: event.query,
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
        created_at: event.timestamp,
        updated_at: event.timestamp,
      });
    }

    const existingAssistantIndex = next.findIndex((m) => m.turn_id === event.turn_id);
    const assistantMsg: ChatMessageDTO = {
      turn_id: event.turn_id,
      thread_id: event.thread_id,
      session_id: event.session_id,
      role: 'assistant',
      content:
        existingAssistantIndex >= 0 ? (next[existingAssistantIndex]?.content ?? '') : '',
      status: 'streaming',
      parent_user_turn_id: event.user_turn_id,
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
      created_at: event.timestamp,
      updated_at: event.timestamp,
    };

    if (existingAssistantIndex >= 0) {
      next[existingAssistantIndex] = assistantMsg;
    } else {
      next.push(assistantMsg);
    }
    return next;
  }

  if (event.event === 'token_chunk') {
    const next = [...currentMessages];
    const targetIdx = next.findIndex((m) => m.turn_id === event.turn_id);
    if (targetIdx >= 0) {
      const target = next[targetIdx]!;
      // Do not append trailing chunks if the turn was already marked interrupted or completed
      if (target.status === 'interrupted' || target.status === 'completed') {
        return next;
      }
      const updatedContent =
        event.accumulated_content.length >= target.content.length
          ? event.accumulated_content
          : target.content + event.delta;
      next[targetIdx] = {
        ...target,
        content: updatedContent,
        status: 'streaming',
        updated_at: event.timestamp,
      };
      return next;
    }

    next.push({
      turn_id: event.turn_id,
      thread_id: event.thread_id,
      session_id: event.session_id,
      role: 'assistant',
      content: event.accumulated_content || event.delta,
      status: 'streaming',
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
      created_at: event.timestamp,
      updated_at: event.timestamp,
    });
    return next;
  }

  if (event.event === 'generation_interrupted') {
    const next = [...currentMessages];
    const targetIdx = next.findIndex((m) => m.turn_id === event.turn_id);
    if (targetIdx >= 0) {
      const target = next[targetIdx]!;
      const preservedContent =
        event.partial_content.length > 0 ? event.partial_content : target.content;
      next[targetIdx] = {
        ...target,
        content: preservedContent,
        status: 'interrupted',
        interrupted_reason: event.reason,
        updated_at: event.timestamp,
      };
      return next;
    }

    next.push({
      turn_id: event.turn_id,
      thread_id: event.thread_id,
      session_id: event.session_id,
      role: 'assistant',
      content: event.partial_content,
      status: 'interrupted',
      parent_user_turn_id: null,
      interrupted_reason: event.reason,
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
      created_at: event.timestamp,
      updated_at: event.timestamp,
    });
    return next;
  }

  if (event.event === 'generation_completed') {
    const next = [...currentMessages];
    const targetIdx = next.findIndex((m) => m.turn_id === event.turn_id);
    const completedMsg: ChatMessageDTO = {
      turn_id: event.turn_id,
      thread_id: event.thread_id,
      session_id: event.session_id,
      role: 'assistant',
      content: event.content,
      status: 'completed',
      parent_user_turn_id:
        targetIdx >= 0 ? (next[targetIdx]?.parent_user_turn_id ?? null) : null,
      interrupted_reason: null,
      is_refusal: event.is_refusal,
      fallback_triggered: event.fallback_triggered,
      trace_id: event.trace_id,
      node_sequence: [...event.node_sequence],
      execution_time_ms: event.execution_time_ms,
      sources: [...event.sources],
      sources_consulted: [...event.sources_consulted],
      tool_calls: [...event.tool_calls],
      memory_proposal: event.memory_proposal,
      recalled_memories: [...event.recalled_memories],
      guardrail_interventions: [...event.guardrail_interventions],
      resolved_country: event.resolved_country,
      created_at:
        targetIdx >= 0 ? (next[targetIdx]?.created_at ?? event.timestamp) : event.timestamp,
      updated_at: event.timestamp,
    };

    if (targetIdx >= 0) {
      next[targetIdx] = completedMsg;
    } else {
      next.push(completedMsg);
    }
    return next;
  }

  if (event.event === 'error' && event.turn_id) {
    const next = [...currentMessages];
    const targetIdx = next.findIndex((m) => m.turn_id === event.turn_id);
    if (targetIdx >= 0) {
      const target = next[targetIdx]!;
      next[targetIdx] = {
        ...target,
        content: target.content.length > 0 ? target.content : event.detail,
        status: 'error',
        updated_at: event.timestamp,
      };
    }
    return next;
  }

  return [...currentMessages];
}
