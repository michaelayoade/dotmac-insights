/**
 * Core API utilities - fetch functions, auth, URL building, timeout, retry, and logging
 */

// Use an internal URL for server-side calls (inside the Docker network) and the public
// NEXT_PUBLIC_API_URL for browser calls. This keeps SSR working while the browser hits
// the host-exposed API port.
export const API_BASE =
  typeof window === 'undefined'
    ? process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || ''
    : process.env.NEXT_PUBLIC_API_URL || '';

// ============================================================================
// TIMEOUT & RETRY CONFIGURATION
// ============================================================================

/** Default request timeout in milliseconds (10 seconds) */
export const DEFAULT_TIMEOUT = 10000;

/** Default retry configuration */
export const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxAttempts: 3,
  baseDelayMs: 2000,
  maxDelayMs: 8000,
  retryOn5xx: true,
  retryOnNetworkError: true,
};

export interface RetryConfig {
  /** Maximum number of retry attempts (default: 3) */
  maxAttempts: number;
  /** Base delay in milliseconds for exponential backoff (default: 2000) */
  baseDelayMs: number;
  /** Maximum delay cap in milliseconds (default: 8000) */
  maxDelayMs: number;
  /** Whether to retry on 5xx server errors (default: true) */
  retryOn5xx: boolean;
  /** Whether to retry on network errors (default: true) */
  retryOnNetworkError: boolean;
}

// ============================================================================
// STRUCTURED LOGGING
// ============================================================================

export interface ApiLog {
  timestamp: string;
  type: 'request' | 'response' | 'error' | 'retry';
  method: string;
  url: string;
  status?: number;
  durationMs?: number;
  error?: string;
  retryAttempt?: number;
  maxAttempts?: number;
}

type ApiLogHandler = (log: ApiLog) => void;

let apiLogHandler: ApiLogHandler | null = null;

/**
 * Register a custom log handler for API requests.
 * Useful for integrating with error tracking services like Sentry.
 */
export function onApiLog(handler: ApiLogHandler): () => void {
  apiLogHandler = handler;
  return () => {
    apiLogHandler = null;
  };
}

// ============================================================================
// PII REDACTION
// ============================================================================

/** Query parameters that may contain PII and should be redacted in logs */
const SENSITIVE_PARAMS = [
  'token',
  'access_token',
  'refresh_token',
  'api_key',
  'apikey',
  'key',
  'secret',
  'password',
  'pwd',
  'auth',
  'authorization',
  'email',
  'phone',
  'ssn',
  'credit_card',
  'card_number',
];

/**
 * Redact sensitive query parameters from a URL for safe logging
 */
function redactUrl(url: string): string {
  try {
    const parsed = new URL(url);
    const redactedParams = new URLSearchParams();

    parsed.searchParams.forEach((value, key) => {
      const lowerKey = key.toLowerCase();
      const isSensitive = SENSITIVE_PARAMS.some(
        (param) => lowerKey.includes(param) || lowerKey === param
      );
      redactedParams.set(key, isSensitive ? '[REDACTED]' : value);
    });

    parsed.search = redactedParams.toString() ? `?${redactedParams.toString()}` : '';
    return parsed.toString();
  } catch {
    // If URL parsing fails, return as-is (relative URLs, etc.)
    return url;
  }
}

function logApi(log: Omit<ApiLog, 'timestamp'>): void {
  const fullLog: ApiLog = {
    ...log,
    timestamp: new Date().toISOString(),
  };

  // Redact sensitive information from URLs before logging
  const safeUrl = redactUrl(log.url);

  // Always log to console in a structured format
  const prefix = `[API ${log.type.toUpperCase()}]`;
  const details = `${log.method} ${safeUrl}`;

  if (log.type === 'error') {
    console.error(prefix, details, log.error, log.retryAttempt ? `(attempt ${log.retryAttempt})` : '');
  } else if (log.type === 'retry') {
    console.warn(prefix, details, `Retry ${log.retryAttempt}/${log.maxAttempts}`, log.error);
  } else if (log.type === 'response') {
    console.debug(prefix, details, `${log.status} in ${log.durationMs}ms`);
  }

  // Call custom handler if registered
  if (apiLogHandler) {
    apiLogHandler(fullLog);
  }
}

// ============================================================================
// URL BUILDING
// ============================================================================

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

// ============================================================================
// AUTHENTICATION
// ============================================================================

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
export async function clearAuthToken(): Promise<void> {
  if (typeof window === 'undefined') {
    return;
  }
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('dotmac_access_token');
  }
  try {
    await fetch(buildApiUrl('/auth/session'), {
      method: 'DELETE',
      credentials: 'include',
    });
  } catch {
    // Ignore network errors when clearing client auth state.
  }
}

/**
 * Set the access token for API calls via httpOnly cookie.
 */
export async function setAuthToken(token: string): Promise<void> {
  if (typeof window === 'undefined') {
    return;
  }
  const response = await fetch(buildApiUrl('/auth/session'), {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: 'Unknown error' }));
    const errorMessage = errorBody.detail || `HTTP ${response.status}`;
    throw new ApiError(response.status, errorMessage, '/auth/session');
  }
}

/**
 * Check if user has a valid auth token stored.
 * Note: httpOnly cookies cannot be read from the browser.
 */
export function hasAuthToken(): boolean {
  if (typeof window !== 'undefined') {
    return false;
  }
  return !!process.env.INTERNAL_SERVICE_TOKEN;
}

function getAccessToken(): string {
  if (typeof window === 'undefined') {
    return process.env.INTERNAL_SERVICE_TOKEN || '';
  }
  return '';
}

// ============================================================================
// ERROR HANDLING
// ============================================================================

/**
 * Error category for UI handling
 */
export type ApiErrorCategory =
  | 'auth'           // 401 - needs login
  | 'forbidden'      // 403 - no permission
  | 'not_found'      // 404 - resource doesn't exist
  | 'validation'     // 422 - invalid data
  | 'server'         // 5xx - server error
  | 'network'        // 0 - connection failed
  | 'timeout'        // request timed out
  | 'unknown';       // other errors

/**
 * Get user-friendly error message based on status and context
 */
function getUserFriendlyMessage(status: number, backendMessage: string, url: string): string {
  // Extract resource type from URL for better messages
  const urlParts = url.replace(/^.*\/api\//, '').split('/').filter(Boolean);
  const resource = urlParts[0]?.replace(/-/g, ' ') || 'resource';

  switch (status) {
    case 0:
      if (backendMessage.includes('timeout')) {
        return 'Request timed out. Please check your connection and try again.';
      }
      return 'Unable to connect to the server. Please check your internet connection.';
    case 400:
      return backendMessage || 'Invalid request. Please check your input and try again.';
    case 401:
      return 'Authentication required. Please sign in.';
    case 403:
      return 'Access denied. You do not have permission to access this resource.';
    case 404:
      // Check if it looks like a specific resource ID was requested
      if (urlParts.length > 1 && /^\d+$/.test(urlParts[urlParts.length - 1])) {
        return `The requested ${resource} could not be found. It may have been deleted or moved.`;
      }
      // Check if backend provided a meaningful message
      if (backendMessage && backendMessage !== 'Not Found' && backendMessage !== 'Not found') {
        return backendMessage;
      }
      return `This ${resource} endpoint is not available. The feature may not be enabled.`;
    case 409:
      return backendMessage || 'This action conflicts with existing data. Please refresh and try again.';
    case 422:
      return backendMessage || 'The provided data is invalid. Please check your input.';
    case 429:
      return 'Too many requests. Please wait a moment and try again.';
    case 500:
      return 'An unexpected server error occurred. Please try again later.';
    case 502:
    case 503:
    case 504:
      return 'The server is temporarily unavailable. Please try again in a few moments.';
    default:
      if (status >= 500) {
        return 'A server error occurred. Please try again later.';
      }
      return backendMessage || `Request failed (${status}). Please try again.`;
  }
}

/**
 * Determine error category from status code
 */
function getErrorCategory(status: number, message: string): ApiErrorCategory {
  if (status === 0) {
    return message.includes('timeout') ? 'timeout' : 'network';
  }
  if (status === 401) return 'auth';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not_found';
  if (status === 422) return 'validation';
  if (status >= 500) return 'server';
  return 'unknown';
}

/**
 * API Error class for handling HTTP errors
 */
export class ApiError extends Error {
  public readonly category: ApiErrorCategory;
  public readonly userMessage: string;

  constructor(
    public status: number,
    message: string,
    url: string = ''
  ) {
    const userMessage = getUserFriendlyMessage(status, message, url);
    super(userMessage);
    this.name = 'ApiError';
    this.category = getErrorCategory(status, message);
    this.userMessage = userMessage;
  }

  /** Check if this error should trigger a retry */
  get isRetryable(): boolean {
    // Retry on server errors (5xx) or network errors (status 0)
    return this.status === 0 || this.status >= 500;
  }

  /** Check if user should be prompted to sign in */
  get requiresAuth(): boolean {
    return this.category === 'auth';
  }

  /** Check if this is a permission error */
  get isForbidden(): boolean {
    return this.category === 'forbidden';
  }

  /** Check if resource wasn't found */
  get isNotFound(): boolean {
    return this.category === 'not_found';
  }

  /** Check if this is a validation error */
  get isValidation(): boolean {
    return this.category === 'validation';
  }
}

// ============================================================================
// FETCH OPTIONS
// ============================================================================

export interface FetchOptions extends RequestInit {
  params?: Record<string, unknown>;
  /** Request timeout in milliseconds (default: 10000) */
  timeout?: number;
  /** Retry configuration, or false to disable retries. By default, only GET requests retry. */
  retry?: Partial<RetryConfig> | false | true;
}

// ============================================================================
// TIMEOUT HANDLING
// ============================================================================

/**
 * Fetch with timeout support using AbortController
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit & { timeout?: number }
): Promise<Response> {
  const { timeout = DEFAULT_TIMEOUT, ...fetchOptions } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });
    return response;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError(0, `Request timeout after ${timeout}ms`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

// ============================================================================
// RETRY LOGIC
// ============================================================================

/**
 * Calculate delay for exponential backoff
 */
function calculateBackoff(attempt: number, config: RetryConfig): number {
  const delay = config.baseDelayMs * Math.pow(2, attempt - 1);
  return Math.min(delay, config.maxDelayMs);
}

/**
 * Sleep for a given duration
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Check if an error should trigger a retry
 */
function shouldRetry(error: unknown, config: RetryConfig): boolean {
  if (error instanceof ApiError) {
    // Don't retry auth errors
    if (error.status === 401 || error.status === 403) {
      return false;
    }
    // Retry 5xx if configured
    if (error.status >= 500 && config.retryOn5xx) {
      return true;
    }
    // Retry network errors if configured
    if (error.status === 0 && config.retryOnNetworkError) {
      return true;
    }
  }
  // Network errors that aren't ApiError
  if (error instanceof TypeError && config.retryOnNetworkError) {
    return true;
  }
  return false;
}

// ============================================================================
// CORE FETCH FUNCTION
// ============================================================================

/**
 * Core fetch function for API calls.
 * Handles authentication, timeout, retry, error handling, and JSON parsing.
 */
export async function fetchApi<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { params, timeout = DEFAULT_TIMEOUT, retry, ...fetchOptions } = options;

  // Build URL
  const base = API_BASE || (typeof window !== 'undefined' ? window.location.origin : '');
  const normalizedEndpoint = endpoint.startsWith('http')
    ? endpoint
    : endpoint.startsWith('/api')
      ? endpoint
      : `/api${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
  let url = endpoint.startsWith('http') ? endpoint : `${base}${normalizedEndpoint}`;

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
  const method = fetchOptions.method || 'GET';

  // Determine if this is an idempotent request (safe to retry)
  const isIdempotent = ['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase());

  // Merge retry config - only retry idempotent methods by default
  // Non-idempotent methods (POST, PUT, PATCH, DELETE) require explicit opt-in
  let retryConfig: RetryConfig | null;
  if (retry === false) {
    retryConfig = null;
  } else if (retry === true) {
    // Explicit opt-in to retry, even for mutations
    retryConfig = { ...DEFAULT_RETRY_CONFIG };
  } else if (typeof retry === 'object') {
    // Custom retry config provided
    retryConfig = { ...DEFAULT_RETRY_CONFIG, ...retry };
  } else if (isIdempotent) {
    // Default: only retry idempotent methods
    retryConfig = { ...DEFAULT_RETRY_CONFIG };
  } else {
    // Default: don't retry mutations
    retryConfig = null;
  }

  const maxAttempts = retryConfig ? retryConfig.maxAttempts : 1;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const startTime = Date.now();

    try {
      // Only set Content-Type for requests with a body to avoid CORS preflight on simple GETs.
      const hasBody = fetchOptions.body !== undefined;
      const isFormData =
        typeof FormData !== 'undefined' && fetchOptions.body instanceof FormData;
      const headers = new Headers(fetchOptions.headers || {});
      if (hasBody && !isFormData && !headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json');
      }
      if (accessToken && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${accessToken}`);
      }

      const response = await fetchWithTimeout(url, {
        ...fetchOptions,
        timeout,
        credentials: typeof window !== 'undefined' ? 'include' : 'omit',
        headers,
      });

      const durationMs = Date.now() - startTime;

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({ detail: 'Unknown error' }));
        const errorMessage = errorBody.detail || `HTTP ${response.status}`;

        // Handle authentication errors globally
        if (response.status === 401) {
          void clearAuthToken();
          if (authEventHandler) {
            authEventHandler('unauthorized', errorMessage);
          }
          logApi({ type: 'error', method, url, status: response.status, error: errorMessage, durationMs });
          throw new ApiError(response.status, errorMessage, url);
        }

        if (response.status === 403) {
          if (authEventHandler) {
            authEventHandler('forbidden', errorMessage);
          }
          logApi({ type: 'error', method, url, status: response.status, error: errorMessage, durationMs });
          throw new ApiError(response.status, errorMessage, url);
        }

        const apiError = new ApiError(response.status, errorMessage, url);

        // Check if we should retry
        if (retryConfig && attempt < maxAttempts && shouldRetry(apiError, retryConfig)) {
          const backoff = calculateBackoff(attempt, retryConfig);
          logApi({
            type: 'retry',
            method,
            url,
            status: response.status,
            error: errorMessage,
            retryAttempt: attempt,
            maxAttempts,
            durationMs,
          });
          await sleep(backoff);
          continue;
        }

        logApi({ type: 'error', method, url, status: response.status, error: errorMessage, durationMs });
        throw apiError;
      }

      // Success
      logApi({ type: 'response', method, url, status: response.status, durationMs });

      if (response.status === 204) {
        return null as T;
      }

      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        return response.json();
      }
      return (await response.text()) as unknown as T;
    } catch (error) {
      const durationMs = Date.now() - startTime;
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';

      // If it's already an ApiError, check if we should retry
      if (error instanceof ApiError) {
        if (retryConfig && attempt < maxAttempts && shouldRetry(error, retryConfig)) {
          const backoff = calculateBackoff(attempt, retryConfig);
          logApi({
            type: 'retry',
            method,
            url,
            error: errorMessage,
            retryAttempt: attempt,
            maxAttempts,
            durationMs,
          });
          await sleep(backoff);
          continue;
        }
        throw error;
      }

      // Network error
      const apiError = new ApiError(0, errorMessage, url);

      if (retryConfig && attempt < maxAttempts && shouldRetry(apiError, retryConfig)) {
        const backoff = calculateBackoff(attempt, retryConfig);
        logApi({
          type: 'retry',
          method,
          url,
          error: errorMessage,
          retryAttempt: attempt,
          maxAttempts,
          durationMs,
        });
        await sleep(backoff);
        continue;
      }

      logApi({ type: 'error', method, url, error: errorMessage, durationMs });
      throw apiError;
    }
  }

  // Should never reach here, but TypeScript needs this
  throw new ApiError(0, 'Max retry attempts exceeded', url);
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
export async function fetchApiFormData<T>(
  endpoint: string,
  formData: FormData,
  options: { timeout?: number; retry?: Partial<RetryConfig> | false | true } = {}
): Promise<T> {
  const { timeout = DEFAULT_TIMEOUT, retry } = options;
  const url = `${API_BASE}/api${endpoint}`;
  const accessToken = getAccessToken();
  const method = 'POST';

  // File uploads are POST (not idempotent) - require explicit opt-in to retry
  let retryConfig: RetryConfig | null;
  if (retry === true) {
    retryConfig = { ...DEFAULT_RETRY_CONFIG };
  } else if (typeof retry === 'object') {
    retryConfig = { ...DEFAULT_RETRY_CONFIG, ...retry };
  } else {
    retryConfig = null;
  }
  const maxAttempts = retryConfig ? retryConfig.maxAttempts : 1;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const startTime = Date.now();

    try {
      const response = await fetchWithTimeout(url, {
        method,
        timeout,
        credentials: typeof window !== 'undefined' ? 'include' : 'omit',
        headers: {
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: formData,
      });

      const durationMs = Date.now() - startTime;

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({ detail: 'Unknown error' }));
        const errorMessage = errorBody.detail || `HTTP ${response.status}`;

        if (response.status === 401) {
          void clearAuthToken();
          if (authEventHandler) {
            authEventHandler('unauthorized', errorMessage);
          }
          logApi({ type: 'error', method, url, status: response.status, error: errorMessage, durationMs });
          throw new ApiError(response.status, errorMessage, url);
        }

        if (response.status === 403) {
          if (authEventHandler) {
            authEventHandler('forbidden', errorMessage);
          }
          logApi({ type: 'error', method, url, status: response.status, error: errorMessage, durationMs });
          throw new ApiError(response.status, errorMessage, url);
        }

        const apiError = new ApiError(response.status, errorMessage, url);

        if (retryConfig && attempt < maxAttempts && shouldRetry(apiError, retryConfig)) {
          const backoff = calculateBackoff(attempt, retryConfig);
          logApi({
            type: 'retry',
            method,
            url,
            status: response.status,
            error: errorMessage,
            retryAttempt: attempt,
            maxAttempts,
            durationMs,
          });
          await sleep(backoff);
          continue;
        }

        logApi({ type: 'error', method, url, status: response.status, error: errorMessage, durationMs });
        throw apiError;
      }

      logApi({ type: 'response', method, url, status: response.status, durationMs });
      return response.json();
    } catch (error) {
      const durationMs = Date.now() - startTime;
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';

      if (error instanceof ApiError) {
        if (retryConfig && attempt < maxAttempts && shouldRetry(error, retryConfig)) {
          const backoff = calculateBackoff(attempt, retryConfig);
          logApi({
            type: 'retry',
            method,
            url,
            error: errorMessage,
            retryAttempt: attempt,
            maxAttempts,
            durationMs,
          });
          await sleep(backoff);
          continue;
        }
        throw error;
      }

      const apiError = new ApiError(0, errorMessage, url);

      if (retryConfig && attempt < maxAttempts && shouldRetry(apiError, retryConfig)) {
        const backoff = calculateBackoff(attempt, retryConfig);
        logApi({
          type: 'retry',
          method,
          url,
          error: errorMessage,
          retryAttempt: attempt,
          maxAttempts,
          durationMs,
        });
        await sleep(backoff);
        continue;
      }

      logApi({ type: 'error', method, url, error: errorMessage, durationMs });
      throw apiError;
    }
  }

  throw new ApiError(0, 'Max retry attempts exceeded', url);
}
