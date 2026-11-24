import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import type { RFPTicketCreatedEventDTO } from '@repo/shared-types';
import { RFPRealtimeNotificationBanner } from '../components/rfp/RFPRealtimeNotificationBanner';

describe('RFPRealtimeNotificationBanner Component Tests', () => {
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

  const mockArrival: RFPTicketCreatedEventDTO = {
    ticket_id: 'tkt_0225',
    rfp_id: 'rfp_0071',
    client_name: 'Northline Apparel',
    client_country: 'US',
    services_requested: ['warehouse', 'lastmile'],
    status: 'analyzing',
    created_at: '2026-11-24T12:00:00Z',
  };

  test('renders connected badge with positive health indicators', () => {
    act(() => {
      root!.render(
        <RFPRealtimeNotificationBanner
          connectionStatus="connected"
          latestArrival={null}
          reconnectAttempt={0}
          onDismissArrival={() => {}}
          onRetryConnection={() => {}}
        />
      );
    });

    const badge = container?.querySelector('[data-testid="sse-connection-badge"]');
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toContain('Tiempo Real Activo (SSE)');
  });

  test('renders reconnecting state with attempt counter and handles manual retry click', () => {
    let retryCalled = false;
    const handleRetry = (): void => {
      retryCalled = true;
    };

    act(() => {
      root!.render(
        <RFPRealtimeNotificationBanner
          connectionStatus="reconnecting"
          latestArrival={null}
          reconnectAttempt={2}
          onDismissArrival={() => {}}
          onRetryConnection={handleRetry}
        />
      );
    });

    const badge = container?.querySelector('[data-testid="sse-connection-badge"]');
    expect(badge?.textContent).toContain('Reconectando canal SSE (intento #2');

    const retryBtn = badge?.querySelector('button');
    expect(retryBtn).not.toBeNull();
    act(() => {
      retryBtn!.click();
    });
    expect(retryCalled).toBe(true);
  });

  test('renders unauthorized and connecting badges accordingly', () => {
    act(() => {
      root!.render(
        <RFPRealtimeNotificationBanner
          connectionStatus="unauthorized"
          latestArrival={null}
          reconnectAttempt={0}
          onDismissArrival={() => {}}
          onRetryConnection={() => {}}
        />
      );
    });

    expect(container?.textContent).toContain('Sesión expirada / No autorizado para canal SSE');

    act(() => {
      root!.render(
        <RFPRealtimeNotificationBanner
          connectionStatus="connecting"
          latestArrival={null}
          reconnectAttempt={0}
          onDismissArrival={() => {}}
          onRetryConnection={() => {}}
        />
      );
    });

    expect(container?.textContent).toContain('Conectando notificaciones en tiempo real...');
  });

  test('renders arrival banner with ticket details and triggers dismiss callback', () => {
    let dismissed = false;
    const handleDismiss = (): void => {
      dismissed = true;
    };

    act(() => {
      root!.render(
        <RFPRealtimeNotificationBanner
          connectionStatus="connected"
          latestArrival={mockArrival}
          reconnectAttempt={0}
          onDismissArrival={handleDismiss}
          onRetryConnection={() => {}}
        />
      );
    });

    const banner = container?.querySelector('[data-testid="rfp-realtime-arrival-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('tkt_0225');
    expect(banner?.textContent).toContain('rfp_0071');
    expect(banner?.textContent).toContain('Northline Apparel');
    expect(banner?.textContent).toContain('US');
    expect(banner?.textContent).toContain('Almacén (Warehouse)');
    expect(banner?.textContent).toContain('Última Milla (Last Mile)');

    const dismissBtn = banner?.querySelector(
      'button[aria-label="Cerrar notificación de nuevo ticket RFP"]'
    ) as HTMLButtonElement | null;
    expect(dismissBtn).not.toBeNull();
    act(() => {
      dismissBtn!.click();
    });
    expect(dismissed).toBe(true);
  });
});
