import { getToken, removeToken } from './auth';

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
 * Centralized fetch wrapper adding authorization headers and handling 401 token invalidation.
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

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });
  } catch (err: unknown) {
    if (err instanceof ApiNetworkError) {
      throw err;
    }
    throw new ApiNetworkError(
      'Unable to connect to the backend server. Please check your network connection.'
    );
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

