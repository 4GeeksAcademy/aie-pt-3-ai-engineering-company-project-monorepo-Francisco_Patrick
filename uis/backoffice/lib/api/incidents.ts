import type {
  Incident,
  IncidentCreateInput,
  IncidentFilterOptions,
  IncidentStatus,
  IncidentSummaryMetrics,
} from '@repo/shared-types';
import { fetchWithAuth } from '../api';

export class IncidentApiError extends Error {
  public fieldErrors?: Record<string, string> | undefined;

  constructor(message: string, fieldErrors?: Record<string, string> | undefined) {
    super(message);
    this.name = 'IncidentApiError';
    this.fieldErrors = fieldErrors;
  }
}

/**
 * Handles API error responses, mapping technical responses to plain language error objects.
 *
 * @param response - The fetch Response object.
 * @returns Throws IncidentApiError with clean user message.
 */
async function handleApiError(response: Response): Promise<never> {
  let errorData: any = null;
  try {
    errorData = await response.json();
  } catch {
    // Non-JSON response body
  }

  if (response.status === 400) {
    const fieldErrors: Record<string, string> = {};

    if (errorData?.details && Array.isArray(errorData.details)) {
      for (const item of errorData.details) {
        if (item.field && item.issue) {
          fieldErrors[item.field] = item.issue;
        }
      }
    }

    const message =
      errorData?.message ||
      'Validation failed. Please check the highlighted fields and try again.';
    throw new IncidentApiError(message, fieldErrors);
  }

  if (response.status === 404) {
    const message =
      errorData?.detail || errorData?.message || 'The requested incident was not found.';
    throw new IncidentApiError(message);
  }

  if (response.status >= 500) {
    throw new IncidentApiError(
      'The incident service is currently experiencing technical difficulties. Please try again later.'
    );
  }

  throw new IncidentApiError(
    errorData?.message || errorData?.detail || 'An unexpected error occurred. Please try again.'
  );
}

/**
 * Creates a new operational incident via POST /api/incidents.
 *
 * @param payload - Incident creation data.
 * @returns Promise resolving to created Incident model.
 * @throws IncidentApiError if validation fails or server error occurs.
 */
export async function createIncident(payload: IncidentCreateInput): Promise<Incident> {
  try {
    const response = await fetchWithAuth('/api/incidents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    return (await response.json()) as Incident;
  } catch (err: unknown) {
    if (err instanceof IncidentApiError) {
      throw err;
    }
    throw new IncidentApiError(
      'Unable to connect to the incident service. Please check your network connection.'
    );
  }
}

/**
 * Retrieves a filtered list of incidents via GET /api/incidents.
 *
 * @param filters - Optional search filters (status, origin, branch, category).
 * @returns Promise resolving to an array of Incident objects.
 * @throws IncidentApiError if request fails.
 */
export async function listIncidents(filters?: IncidentFilterOptions): Promise<Incident[]> {
  try {
    const params = new URLSearchParams();
    if (filters?.status) params.append('status', filters.status);
    if (filters?.origin) params.append('origin', filters.origin);
    if (filters?.branch) params.append('branch', filters.branch);
    if (filters?.category) params.append('category', filters.category);

    const queryString = params.toString() ? `?${params.toString()}` : '';
    const response = await fetchWithAuth(`/api/incidents${queryString}`, {
      method: 'GET',
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    return (await response.json()) as Incident[];
  } catch (err: unknown) {
    if (err instanceof IncidentApiError) {
      throw err;
    }
    throw new IncidentApiError(
      'Unable to load incidents list. Please check your network connection.'
    );
  }
}

/**
 * Fetches single incident detail by ID via GET /api/incidents/{id}.
 *
 * @param id - Unique incident identifier.
 * @returns Promise resolving to Incident object.
 * @throws IncidentApiError if incident missing or request fails.
 */
export async function getIncidentById(id: string): Promise<Incident> {
  try {
    const response = await fetchWithAuth(`/api/incidents/${encodeURIComponent(id)}`, {
      method: 'GET',
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    return (await response.json()) as Incident;
  } catch (err: unknown) {
    if (err instanceof IncidentApiError) {
      throw err;
    }
    throw new IncidentApiError(
      'Unable to load incident details. Please check your network connection.'
    );
  }
}

/**
 * Updates status of an existing incident via PATCH /api/incidents/{id}/status.
 *
 * @param id - Unique incident identifier.
 * @param status - Target status string.
 * @returns Promise resolving to updated Incident object.
 * @throws IncidentApiError if transition is invalid or request fails.
 */
export async function updateIncidentStatus(
  id: string,
  status: IncidentStatus
): Promise<Incident> {
  try {
    const response = await fetchWithAuth(`/api/incidents/${encodeURIComponent(id)}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    return (await response.json()) as Incident;
  } catch (err: unknown) {
    if (err instanceof IncidentApiError) {
      throw err;
    }
    throw new IncidentApiError(
      'Unable to update incident status. Please check your network connection.'
    );
  }
}

/**
 * Fetches 4-dimension operational summary metrics via GET /api/incidents/summary.
 *
 * @returns Promise resolving to IncidentSummaryMetrics.
 * @throws IncidentApiError if request fails.
 */
export async function getIncidentSummary(): Promise<IncidentSummaryMetrics> {
  try {
    const response = await fetchWithAuth('/api/incidents/summary', {
      method: 'GET',
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    return (await response.json()) as IncidentSummaryMetrics;
  } catch (err: unknown) {
    if (err instanceof IncidentApiError) {
      throw err;
    }
    throw new IncidentApiError(
      'Unable to load summary metrics. Please check your network connection.'
    );
  }
}
