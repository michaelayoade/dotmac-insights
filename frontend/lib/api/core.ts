/**
 * Core API utilities - fetch functions, auth, and URL building
 */

// Use an internal URL for server-side calls (inside the Docker network) and the public
// NEXT_PUBLIC_API_URL for browser calls. This keeps SSR working while the browser hits
// the host-exposed API port.
export const API_BASE =
  typeof window === 'undefined'
    ? process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || ''
    : process.env.NEXT_PUBLIC_API_URL || '';

/**
 * Build a full API URL with query parameters
 */
export function buildApiUrl(
  endpoint: string,
  params?: Record<string, string | number | boolean | undefined>
): string {
  const base = API_BASE || (typeof window !== 'undefined' ? window.location.origin : '');
  const normalizedEndpoint = endpoint.startsWith('http')
    ? endpoint
    : `${base}${endpoint.startsWith('/api') ? endpoint : `/api${endpoint}`}`;
  const url = new URL(normalizedEndpoint);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return;
      url.searchParams.append(key, String(value));
    });
  }
  return url.toString();
}

/**
 * Build a query string from params object
 */
export function buildQueryString(
  params?: Record<string, string | number | boolean | undefined | null>
): string {
  if (!params) return '';
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value));
    }
  });
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : '';
}

// Auth event types for global handling
export type AuthEventType = 'unauthorized' | 'forbidden' | 'token_expired';
export type AuthEventHandler = (event: AuthEventType, message?: string) => void;

let authEventHandler: AuthEventHandler | null = null;

/**
 * Register a global auth event handler for 401/403 responses.
 * This should be called once in the app root to handle auth state globally.
 */
export function onAuthError(handler: AuthEventHandler): () => void {
  authEventHandler = handler;
  return () => {
    authEventHandler = null;
  };
}

/**
 * Clear the stored access token and trigger re-authentication.
 */
export function clearAuthToken(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('dotmac_access_token');
  }
}

/**
 * Set the access token for API calls.
 */
export function setAuthToken(token: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('dotmac_access_token', token);
  }
}

/**
 * Check if user has a valid auth token stored.
 */
export function hasAuthToken(): boolean {
  if (typeof window !== 'undefined') {
    return !!localStorage.getItem('dotmac_access_token');
  }
  return false;
}

// Check if we're in development mode - service token should only work in dev
const isDevelopment = process.env.NODE_ENV === 'development';

function getAccessToken(): string {
  if (typeof window !== 'undefined') {
    // Client-side: only use stored user token
    const token = localStorage.getItem('dotmac_access_token');
    if (token) return token;

    // Fallback: allow NEXT_PUBLIC_SERVICE_TOKEN only in development
    if (isDevelopment && process.env.NEXT_PUBLIC_SERVICE_TOKEN) {
      return process.env.NEXT_PUBLIC_SERVICE_TOKEN;
    }
    return '';
  }
  // Server-side fallback for SSR/exports - only in development
  if (isDevelopment && process.env.NEXT_PUBLIC_SERVICE_TOKEN) {
    return process.env.NEXT_PUBLIC_SERVICE_TOKEN;
  }
  return '';
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface FetchOptions extends RequestInit {
  params?: Record<string, any>;
}

/**
 * API Error class for handling HTTP errors
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Core fetch function for API calls.
 * Handles authentication, error handling, and JSON parsing.
 */
export async function fetchApi<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { params, ...fetchOptions } = options;

  let url = `${API_BASE}/api${endpoint}`;

  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  const accessToken = getAccessToken();

  let response: Response;
  try {
    response = await fetch(url, {
      ...fetchOptions,
      // Don't include credentials for cross-origin requests with Bearer token
      // CORS with credentials: 'include' requires specific origin header, not wildcard '*'
      credentials: accessToken ? 'omit' : 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...fetchOptions.headers,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unable to reach the API';
    throw new ApiError(0, `Network error: ${message}`);
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    const errorMessage = error.detail || `HTTP ${response.status}`;

    // Handle authentication errors globally
    if (response.status === 401) {
      clearAuthToken();
      if (authEventHandler) {
        authEventHandler('unauthorized', errorMessage);
      }
      throw new ApiError(response.status, 'Authentication required. Please sign in.');
    }

    if (response.status === 403) {
      if (authEventHandler) {
        authEventHandler('forbidden', errorMessage);
      }
      throw new ApiError(
        response.status,
        'Access denied. You do not have permission to access this resource.'
      );
    }

    throw new ApiError(response.status, errorMessage);
  }

  return response.json();
}

/**
 * SWR-compatible fetcher function for GET requests.
 * Wraps fetchApi for use with useSWR.
 */
export async function fetcher<T>(endpoint: string): Promise<T> {
  return fetchApi<T>(endpoint);
}

/**
 * Generic API fetch function for mutations (POST, PATCH, PUT, DELETE).
 * Exported for use in custom hooks.
 */
export async function apiFetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  return fetchApi<T>(endpoint, options);
}

/**
 * Fetch API with FormData support for file uploads.
 * Does not set Content-Type header - browser sets it with boundary for multipart/form-data.
 */
export async function fetchApiFormData<T>(endpoint: string, formData: FormData): Promise<T> {
  const url = `${API_BASE}/api${endpoint}`;
  const accessToken = getAccessToken();

  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      credentials: accessToken ? 'omit' : 'include',
      headers: {
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        // Note: Do NOT set Content-Type for FormData - browser sets it with boundary
      },
      body: formData,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unable to reach the API';
    throw new ApiError(0, `Network error: ${message}`);
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    const errorMessage = error.detail || `HTTP ${response.status}`;

    if (response.status === 401) {
      clearAuthToken();
      if (authEventHandler) {
        authEventHandler('unauthorized', errorMessage);
      }
      throw new ApiError(response.status, 'Authentication required. Please sign in.');
    }

    if (response.status === 403) {
      if (authEventHandler) {
        authEventHandler('forbidden', errorMessage);
      }
      throw new ApiError(
        response.status,
        'Access denied. You do not have permission to access this resource.'
      );
    }

    throw new ApiError(response.status, errorMessage);
  }

  return response.json();
}
