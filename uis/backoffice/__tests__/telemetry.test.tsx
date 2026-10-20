import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import type {
  DailyEventVolumeMetric,
  ErrorDistributionMetric,
  AuthFailureRateMetric,
  TelemetryReportResponse,
} from '@repo/shared-types';
import EventVolumeChart from '../components/telemetry/EventVolumeChart';
import ErrorDistribution from '../components/telemetry/ErrorDistribution';
import AuthFailureCard from '../components/telemetry/AuthFailureCard';
import TelemetryDashboardPage from '../app/telemetry/page';
import { fetchTelemetryReport } from '../lib/telemetryApi';

// Mock the Next.js router and auth
jest.mock('next/navigation', () => ({
  useRouter: (): { push: jest.Mock } => ({ push: jest.fn() }),
  usePathname: (): string => '/telemetry',
}));

jest.mock('../lib/auth', () => ({
  isAuthenticated: (): boolean => true,
  getToken: (): string => 'mock-token',
  removeToken: jest.fn(),
}));

const mockDailyVolume: readonly DailyEventVolumeMetric[] = [
  { date: '2026-10-10', count: 120 },
  { date: '2026-10-11', count: 85 },
  { date: '2026-10-12', count: 210 },
];

const mockErrorDistribution: readonly ErrorDistributionMetric[] = [
  { event_type: 'auth_login_failed', count: 24, percentage: 60.0 },
  { event_type: 'stock_threshold_triggered', count: 16, percentage: 40.0 },
];

const mockAuthFailure: readonly AuthFailureRateMetric[] = [
  { date: '2026-10-10', total_attempts: 100, failed_attempts: 10, failure_rate: 0.1 },
  { date: '2026-10-11', total_attempts: 50, failed_attempts: 0, failure_rate: 0.0 },
];

const mockReport: TelemetryReportResponse = {
  period: {
    from: '2026-10-10T00:00:00Z',
    to: '2026-10-17T00:00:00Z',
  },
  metrics: {
    events_per_day: [...mockDailyVolume],
    error_rate_by_type: [...mockErrorDistribution],
    auth_failure_rate: [...mockAuthFailure],
  },
};

describe('Telemetry Visual Dashboard Components (Phase 6 / User Story 4)', () => {
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

  describe('EventVolumeChart (T021)', () => {
    test('renders daily volume bars and dates accurately', async () => {
      await act(async () => {
        root!.render(<EventVolumeChart data={mockDailyVolume} />);
      });

      expect(container?.textContent).toContain('Daily Event Volume');
      expect(container?.textContent).toContain('2026-10-10');
      expect(container?.textContent).toContain('120');
      expect(container?.textContent).toContain('2026-10-12');
      expect(container?.textContent).toContain('210');

      const svgBars = container?.querySelectorAll('[data-testid="event-volume-bar"]');
      expect(svgBars?.length).toBe(3);
    });

    test('renders empty state when volume data array is empty', async () => {
      await act(async () => {
        root!.render(<EventVolumeChart data={[]} />);
      });

      expect(container?.textContent).toContain('No event volume data available');
    });
  });

  describe('ErrorDistribution (T022)', () => {
    test('renders table of error categories with counts and percentages', async () => {
      await act(async () => {
        root!.render(<ErrorDistribution data={mockErrorDistribution} />);
      });

      expect(container?.textContent).toContain('Operational Error Distribution');
      expect(container?.textContent).toContain('auth_login_failed');
      expect(container?.textContent).toContain('24');
      expect(container?.textContent).toContain('60.0%');
      expect(container?.textContent).toContain('stock_threshold_triggered');
      expect(container?.textContent).toContain('40.0%');
    });

    test('renders healthy status empty state when error distribution is empty', async () => {
      await act(async () => {
        root!.render(<ErrorDistribution data={[]} />);
      });

      expect(container?.textContent).toContain('Zero Operational Errors');
      expect(container?.textContent).toContain('No errors detected during the reporting window');
    });
  });

  describe('AuthFailureCard (T023)', () => {
    test('renders aggregated auth failure rates and daily time series', async () => {
      await act(async () => {
        root!.render(<AuthFailureCard data={mockAuthFailure} />);
      });

      expect(container?.textContent).toContain('Authentication Flow Reliability');
      expect(container?.textContent).toContain('150'); // 100 + 50
      expect(container?.textContent).toContain('10'); // 10 failed
      expect(container?.textContent).toContain('6.7%'); // 10/150 = 6.6667%
      expect(container?.textContent).toContain('2026-10-10');
      expect(container?.textContent).toContain('10.0%');
    });

    test('renders clean zero-division safe state when attempts are zero', async () => {
      const zeroAttempts: readonly AuthFailureRateMetric[] = [
        { date: '2026-10-15', total_attempts: 0, failed_attempts: 0, failure_rate: 0.0 },
      ];

      await act(async () => {
        root!.render(<AuthFailureCard data={zeroAttempts} />);
      });

      expect(container?.textContent).toContain('0.0%');
      expect(container?.textContent).toContain('Total Attempts: 0');
    });

    test('renders empty state when auth data array is empty', async () => {
      await act(async () => {
        root!.render(<AuthFailureCard data={[]} />);
      });

      expect(container?.textContent).toContain('No authentication activity recorded');
    });
  });

  describe('TelemetryDashboardPage (T024)', () => {
    test('fetches and renders report metrics with active time window on mount', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'X-Cache': 'HIT' }),
        json: async (): Promise<TelemetryReportResponse> => mockReport,
      } as Response);

      await act(async () => {
        root!.render(<TelemetryDashboardPage />);
      });

      // Wait for fetch resolution
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 10));
      });

      expect(container?.textContent).toContain('Telemetry & Operational Health');
      expect(container?.textContent).toContain('2026-10-10T00:00:00Z');
      expect(container?.textContent).toContain('2026-10-17T00:00:00Z');
      expect(container?.textContent).toContain('HIT');
      expect(container?.textContent).toContain('Daily Event Volume');
      expect(container?.textContent).toContain('Operational Error Distribution');
      expect(container?.textContent).toContain('Authentication Flow Reliability');
    });

    test('displays error alert with retry button on network failure', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network offline'));

      await act(async () => {
        root!.render(<TelemetryDashboardPage />);
      });

      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 10));
      });

      expect(container?.textContent).toContain('Failed to Load Telemetry Report');
      const retryButton = container?.querySelector('button[data-testid="retry-telemetry-btn"]');
      expect(retryButton).toBeDefined();

      // Trigger retry
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'X-Cache': 'MISS' }),
        json: async (): Promise<TelemetryReportResponse> => mockReport,
      } as Response);

      await act(async () => {
        retryButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });

      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 10));
      });

      expect(container?.textContent).toContain('Daily Event Volume');
    });
  });

  describe('fetchTelemetryReport client API', () => {
    test('calls /telemetry/report and formats ISO query parameters', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        headers: new Headers(),
        json: async (): Promise<TelemetryReportResponse> => mockReport,
      } as Response);

      const result = await fetchTelemetryReport({
        start_date: '2026-10-10T00:00:00Z',
        end_date: '2026-10-17T00:00:00Z',
      });

      expect(result).toEqual(mockReport);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/telemetry/report?start_date=2026-10-10T00%3A00%3A00Z&end_date=2026-10-17T00%3A00%3A00Z'),
        expect.anything()
      );
    });

    test('throws descriptive error on HTTP failure status', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 422,
        headers: new Headers(),
        json: async (): Promise<{ detail: string }> => ({ detail: 'start_date must be before end_date' }),
      } as Response);

      await expect(
        fetchTelemetryReport({
          start_date: '2026-10-20T00:00:00Z',
          end_date: '2026-10-10T00:00:00Z',
        })
      ).rejects.toThrow('start_date must be before end_date');
    });
  });
});
