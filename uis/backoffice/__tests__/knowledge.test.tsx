import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import type { KnowledgeQueryResponseDTO } from '@repo/shared-types';
import KnowledgeQueryForm from '../components/knowledge/KnowledgeQueryForm';
import KnowledgeAnswerCard from '../components/knowledge/KnowledgeAnswerCard';
import KnowledgeStatusState from '../components/knowledge/KnowledgeStatusState';
import KnowledgeBasePage from '../app/knowledge/page';

jest.mock('next/navigation', () => ({
  useRouter: (): { push: jest.Mock } => ({ push: jest.fn() }),
  usePathname: (): string => '/knowledge',
}));

const mockGroundedResponse: KnowledgeQueryResponseDTO = {
  query: "What is TrackFlow's standard return window and who covers return shipping costs?",
  answer:
    "TrackFlow's standard return window is 30 days from delivery, unless the client brand has configured a custom window in their contract. Return shipping costs are covered by the client brand under normal circumstances; TrackFlow covers return shipping only when caused by a TrackFlow error.",
  is_refusal: false,
  sources: [
    {
      source_document: 'returns-policy',
      section: 'Standard Return Window & Return Shipping Costs',
      similarity_score: 0.96,
    },
  ],
  execution_time_ms: 42.5,
};

const mockRefusalResponse: KnowledgeQueryResponseDTO = {
  query: "What is TrackFlow's temperature-controlled pharmaceutical refrigeration SLA?",
  answer:
    'TrackFlow internal documentation does not contain verified policy regarding this inquiry. For operational assistance on this topic, please consult the operations leadership directly.',
  is_refusal: true,
  sources: [],
  execution_time_ms: 18.2,
};

describe('Knowledge Base Frontline UI Components & Page (Phase 6 / User Story 4)', () => {
  let container: HTMLDivElement | null = null;
  let root: Root | null = null;
  const originalFetch = global.fetch;

  beforeAll(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  });

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    global.fetch = jest.fn();
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
    global.fetch = originalFetch;
    jest.clearAllMocks();
  });

  describe('KnowledgeQueryForm (T030)', () => {
    test('rejects empty or whitespace-only queries with validation error and prevents submission', async () => {
      const handleSubmit = jest.fn();

      await act(async () => {
        root!.render(<KnowledgeQueryForm onSubmit={handleSubmit} isLoading={false} />);
      });

      const form = container?.querySelector('form');
      expect(form).not.toBeNull();

      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(handleSubmit).not.toHaveBeenCalled();
      expect(container?.textContent).toContain(
        'Please enter a policy or operational question before submitting.'
      );
    });

    test('submits trimmed valid query when form is submitted', async () => {
      const handleSubmit = jest.fn();

      await act(async () => {
        root!.render(
          <KnowledgeQueryForm
            onSubmit={handleSubmit}
            isLoading={false}
            initialQuery="  What is the return window?  "
          />
        );
      });

      const form = container?.querySelector('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(handleSubmit).toHaveBeenCalledWith('What is the return window?');
    });
  });

  describe('KnowledgeAnswerCard (T031)', () => {
    test('renders grounded answer text, confidence badge, and source citations', async () => {
      await act(async () => {
        root!.render(<KnowledgeAnswerCard response={mockGroundedResponse} />);
      });

      expect(container?.textContent).toContain('Verified Policy Grounded');
      expect(container?.textContent).toContain('30 days from delivery');
      expect(container?.textContent).toContain('Returns & Reverse Logistics Policy');
      expect(container?.textContent).toContain('Standard Return Window & Return Shipping Costs');
      expect(container?.textContent).toContain('96% match');
    });

    test('renders refusal status indicator and empty sources notice on out-of-scope response', async () => {
      await act(async () => {
        root!.render(<KnowledgeAnswerCard response={mockRefusalResponse} />);
      });

      expect(container?.textContent).toContain('Unverified / Out of Scope');
      expect(container?.textContent).toContain(
        'No corporate policy chunks met the calibrated 0.62 minimum similarity threshold.'
      );
    });
  });

  describe('KnowledgeStatusState (T032)', () => {
    test('renders loading skeleton when isLoading is true', async () => {
      await act(async () => {
        root!.render(<KnowledgeStatusState isLoading={true} errorMessage={null} />);
      });

      const skeleton = container?.querySelector('[data-testid="knowledge-loading-skeleton"]');
      expect(skeleton).not.toBeNull();
    });

    test('renders error alert and triggers onRetry callback when clicked', async () => {
      const handleRetry = jest.fn();

      await act(async () => {
        root!.render(
          <KnowledgeStatusState
            isLoading={false}
            errorMessage="Qdrant service unreachable"
            onRetry={handleRetry}
          />
        );
      });

      expect(container?.textContent).toContain('Knowledge Base Service Interruption');
      expect(container?.textContent).toContain('Qdrant service unreachable');

      const retryBtn = container?.querySelector('button[data-testid="knowledge-retry-btn"]');
      expect(retryBtn).not.toBeNull();

      await act(async () => {
        retryBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });

      expect(handleRetry).toHaveBeenCalledTimes(1);
    });
  });

  describe('KnowledgeBasePage (T033)', () => {
    test('submits sample query, displays answer card, and recovers from network error via retry', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network connection lost'));

      await act(async () => {
        root!.render(<KnowledgeBasePage />);
      });

      // Click first sample query button
      const sampleButtons = container?.querySelectorAll('button[type="button"]');
      const firstSample = sampleButtons?.[0];
      expect(firstSample).toBeDefined();

      await act(async () => {
        firstSample?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });

      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 10));
      });

      expect(container?.textContent).toContain('Knowledge Base Service Interruption');
      expect(container?.textContent).toContain('Network connection lost');

      // Now mock successful response on retry
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async (): Promise<KnowledgeQueryResponseDTO> => mockGroundedResponse,
      } as Response);

      const retryBtn = container?.querySelector('button[data-testid="knowledge-retry-btn"]');
      expect(retryBtn).not.toBeNull();

      await act(async () => {
        retryBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });

      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 10));
      });

      expect(container?.textContent).toContain('30 days from delivery');
      expect(container?.textContent).toContain('Returns & Reverse Logistics Policy');
    });
  });
});
