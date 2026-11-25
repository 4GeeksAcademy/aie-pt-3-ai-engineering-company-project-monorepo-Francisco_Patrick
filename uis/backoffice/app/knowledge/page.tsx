'use client';

import React, { useState, useCallback } from 'react';
import type {
  KnowledgeQueryRequestDTO,
  KnowledgeQueryResponseDTO,
} from '@repo/shared-types';
import KnowledgeQueryForm from '../../components/knowledge/KnowledgeQueryForm';
import KnowledgeAnswerCard from '../../components/knowledge/KnowledgeAnswerCard';
import KnowledgeStatusState from '../../components/knowledge/KnowledgeStatusState';
import SupportAgentChatPanel from '../../components/knowledge/SupportAgentChatPanel';
import { useSupportAgentChat } from '../../hooks/useSupportAgentChat';

const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

/**
 * Submit a natural-language policy query to the backend knowledge base endpoint.
 *
 * @param payload - Typed KnowledgeQueryRequestDTO containing query and retrieval options.
 * @returns Resolved KnowledgeQueryResponseDTO from POST /api/v1/knowledge/query.
 * @throws Error when network request fails or returns a non-2xx HTTP status.
 */
async function submitKnowledgeQuery(
  payload: KnowledgeQueryRequestDTO
): Promise<KnowledgeQueryResponseDTO> {
  const response = await fetch(`${API_BASE_URL}/api/v1/knowledge/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMessage = `Knowledge service returned HTTP ${response.status}`;
    try {
      const errBody = (await response.json()) as {
        message?: string;
        detail?: string;
      };
      if (typeof errBody.message === 'string' && errBody.message.length > 0) {
        errorMessage = errBody.message;
      } else if (typeof errBody.detail === 'string' && errBody.detail.length > 0) {
        errorMessage = errBody.detail;
      }
    } catch {
      // Fallback to status message if error response is not valid JSON
    }
    throw new Error(errorMessage);
  }

  return (await response.json()) as KnowledgeQueryResponseDTO;
}

/**
 * Frontline Interactive Knowledge Base, RAG Query & Real-Time Support Agent Streaming Chat Page (`/knowledge`).
 *
 * Hosts both:
 * 1. The synchronous Single-Turn Policy Lookup form (`POST /api/v1/knowledge/query`), and
 * 2. The full-duplex Bidirectional WebSocket Support Agent Streaming Chat (`/api/v1/agent/ws`)
 *    with progressive token rendering, true mid-stream generation abort (`Interrupt / Stop`),
 *    partial response preservation (`status: "interrupted"`), instant redirection, and automatic
 *    progressive-backoff reconnection with thread rehydration.
 *
 * @returns Rendered JSX page element.
 */
export default function KnowledgeBasePage(): React.ReactElement {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [answerResponse, setAnswerResponse] =
    useState<KnowledgeQueryResponseDTO | null>(null);
  const [lastQuery, setLastQuery] = useState<string>('');

  const chat = useSupportAgentChat({
    apiUrl: API_BASE_URL,
  });

  const executeQuery = useCallback(async (queryText: string): Promise<void> => {
    setLastQuery(queryText);
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const result = await submitKnowledgeQuery({
        query: queryText,
        language: 'en',
        top_k: 3,
      });
      setAnswerResponse(result);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : 'Unable to reach the TrackFlow Knowledge Base service. Please check your connection and try again.';
      setErrorMessage(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleRetry = useCallback((): void => {
    if (lastQuery.trim().length >= 3) {
      void executeQuery(lastQuery);
    }
  }, [executeQuery, lastQuery]);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <header className="space-y-1">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Commercial &amp; Operations Knowledge Base
            </h1>
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-950/80 text-emerald-300 border border-emerald-800/60">
              Qdrant RAG • Grounded Policy Assistant
            </span>
          </div>
          <p className="text-sm text-slate-400">
            Query verified TrackFlow agreements on Delivery SLAs, Returns Policy, Carrier Coverage,
            and Warehouse Storage Pricing with zero hallucination and strict governance guardrails.
          </p>
        </header>

        <KnowledgeQueryForm
          onSubmit={executeQuery}
          isLoading={isLoading}
          initialQuery={lastQuery}
        />

        <KnowledgeStatusState
          isLoading={isLoading}
          errorMessage={errorMessage}
          onRetry={lastQuery.length >= 3 ? handleRetry : undefined}
        />

        {!isLoading && errorMessage === null && answerResponse !== null ? (
          <KnowledgeAnswerCard response={answerResponse} />
        ) : null}

        <SupportAgentChatPanel
          messages={chat.messages}
          connectionStatus={chat.connectionStatus}
          threadId={chat.threadId}
          isStreaming={chat.isStreaming}
          pendingProposal={chat.pendingProposal}
          errorMessage={chat.errorMessage}
          reconnectAttempt={chat.reconnectAttempt}
          onSendMessage={chat.sendMessage}
          onInterrupt={chat.interruptGeneration}
          onReconnect={chat.reconnectNow}
          onNewThread={chat.startNewThread}
          onProposalFeedback={chat.submitProposalFeedback}
        />
      </div>
    </main>
  );
}
