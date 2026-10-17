import type {
  TelemetryReportQueryParams,
  TelemetryReportResponse,
} from '@repo/shared-types';
import { fetchWithAuth } from './api';

export interface TelemetryReportFetchResult {
  readonly report: TelemetryReportResponse;
  readonly xCache: string | null;
}

/**
 * Fetches the operational telemetry report from the backend reporting endpoint.
 *
 * @param params - Optional query parameters including start_date and end_date in ISO 8601 UTC format.
 * @returns Promise resolving to the validated TelemetryReportResponse.
 * @throws Error if the HTTP response is not ok or network fails.
 */
export async function fetchTelemetryReport(
  params?: TelemetryReportQueryParams
): Promise<TelemetryReportResponse> {
  const queryParts: string[] = [];
  if (params?.start_date) {
    queryParts.push(`start_date=${encodeURIComponent(params.start_date)}`);
  }
  if (params?.end_date) {
    queryParts.push(`end_date=${encodeURIComponent(params.end_date)}`);
  }

  const queryString = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';
  const response = await fetchWithAuth(`/telemetry/report${queryString}`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    let errorDetail = `Telemetry report request failed with HTTP ${response.status}`;
    try {
      const errorJson = (await response.json()) as { detail?: string };
      if (errorJson.detail) {
        errorDetail = errorJson.detail;
      }
    } catch {
      // Non-JSON error payload
    }
    throw new Error(errorDetail);
  }

  const data = (await response.json()) as TelemetryReportResponse;
  return data;
}
