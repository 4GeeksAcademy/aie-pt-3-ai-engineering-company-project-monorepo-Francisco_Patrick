import { getToken, removeToken } from './auth';
import { track } from '../app/services/telemetry';

const API_BASE_URL: string = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Field-level validation error details returned by backend validation handlers.
 */
export interface ApiValidationErrorDetail {
  readonly field: string;
  readonly issue: string;
}

/**
 * Standardized backend JSON error response payload schema.
 */
export interface ApiErrorPayload {
  readonly error: string;
  readonly message: string;
  readonly detail?: string | undefined;
  readonly details?: readonly ApiValidationErrorDetail[] | undefined;
}

/**
 * Custom error class thrown when low-level network connectivity or DNS drops occur.
 */
export class ApiNetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiNetworkError';
  }
}

/**
 * Custom error class thrown when backend responds with a non-2xx status code.
 */
export class ApiServerError extends Error {
  public readonly statusCode: number;
  public readonly payload?: ApiErrorPayload | undefined;

  constructor(statusCode: number, message: string, payload?: ApiErrorPayload | undefined) {
    super(message);
    this.name = 'ApiServerError';
    this.statusCode = statusCode;
    this.payload = payload;
  }
}

export interface FetchOptions extends Omit<RequestInit, 'headers'> {
  headers?: Record<string, string>;
}

/**
 * Centralized fetch wrapper adding authorization headers, handling 401 token invalidation,
 * and emitting api_latency_recorded telemetry.
 *
 * @param endpoint - Relative API path starting with slash (e.g. '/api/incidents').
 * @param options - Standard fetch request initialization options.
 * @returns Promise resolving to the HTTP Response object.
 */
export async function fetchWithAuth(endpoint: string, options: FetchOptions = {}): Promise<Response> {
  const token = getToken();
  
  const headers: Record<string, string> = {
    ...(options.headers ?? {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH" = 
    ((options.method?.toUpperCase() as "GET" | "POST" | "PUT" | "DELETE" | "PATCH") || "GET");
  const startTime = typeof performance !== 'undefined' ? performance.now() : Date.now();

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });
  } catch (err: unknown) {
    const elapsed = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - startTime;
    if (!endpoint.includes('/telemetry/')) {
      track('api_latency_recorded', {
        endpointPath: endpoint,
        httpMethod: method,
        durationMs: Math.round(elapsed * 100) / 100,
        httpStatusCode: 0,
        success: false,
      });
    }

    if (err instanceof ApiNetworkError) {
      throw err;
    }
    throw new ApiNetworkError(
      'Unable to connect to the backend server. Please check your network connection.'
    );
  }

  const elapsed = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - startTime;
  if (!endpoint.includes('/telemetry/')) {
    track('api_latency_recorded', {
      endpointPath: endpoint,
      httpMethod: method,
      durationMs: Math.round(elapsed * 100) / 100,
      httpStatusCode: response.status,
      success: response.ok,
    });
  }

  if (response.status === 401) {
    // Token is invalid or expired
    removeToken();
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
  }

  return response;
}

