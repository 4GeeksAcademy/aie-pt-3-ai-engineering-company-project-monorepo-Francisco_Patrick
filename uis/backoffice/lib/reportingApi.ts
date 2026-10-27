import type {
  ExecutiveKpisResponse,
  PipelineStatusResponse,
  ReportingQueryParams,
} from '@repo/shared-types';
import { fetchWithAuth } from './api';

/**
 * Fetches pre-aggregated executive performance KPI snapshots from the backend reporting endpoint.
 *
 * @param params - Optional query parameters including country ('US', 'ES', 'GLOBAL'), start_date, and end_date.
 * @returns Promise resolving to the validated ExecutiveKpisResponse containing snapshot records.
 * @throws Error if the HTTP response status is not 2xx or network communication fails.
 */
export async function fetchExecutiveKpis(
  params?: ReportingQueryParams
): Promise<ExecutiveKpisResponse> {
  const queryParts: string[] = [];
  if (params?.country) {
    queryParts.push(`country=${encodeURIComponent(params.country)}`);
  }
  if (params?.start_date) {
    queryParts.push(`start_date=${encodeURIComponent(params.start_date)}`);
  }
  if (params?.end_date) {
    queryParts.push(`end_date=${encodeURIComponent(params.end_date)}`);
  }

  const queryString = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';
  const response = await fetchWithAuth(`/reporting/kpis${queryString}`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    let errorDetail = `Executive KPIs request failed with HTTP ${response.status}`;
    try {
      const errorJson = (await response.json()) as { detail?: string };
      if (errorJson.detail) {
        errorDetail = errorJson.detail;
      }
    } catch {
      // Response was not JSON
    }
    throw new Error(errorDetail);
  }

  const data = (await response.json()) as ExecutiveKpisResponse;
  return data;
}

/**
 * Fetches the execution status and operational health of the latest reporting pipeline flow run.
 *
 * @returns Promise resolving to the PipelineStatusResponse.
 * @throws Error if the HTTP response status is not 2xx or network communication fails.
 */
export async function fetchPipelineStatus(): Promise<PipelineStatusResponse> {
  const response = await fetchWithAuth('/reporting/status', {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    let errorDetail = `Pipeline status request failed with HTTP ${response.status}`;
    try {
      const errorJson = (await response.json()) as { detail?: string };
      if (errorJson.detail) {
        errorDetail = errorJson.detail;
      }
    } catch {
      // Response was not JSON
    }
    throw new Error(errorDetail);
  }

  const data = (await response.json()) as PipelineStatusResponse;
  return data;
}
