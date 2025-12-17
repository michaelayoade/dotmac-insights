/**
 * Centralized environment variable management with validation and type safety.
 * All environment variables should be accessed through this module.
 */

// Environment types
type Environment = 'development' | 'production' | 'test';

interface EnvConfig {
  // App
  NODE_ENV: Environment;
  IS_DEVELOPMENT: boolean;
  IS_PRODUCTION: boolean;
  IS_TEST: boolean;

  // API
  API_URL: string;
  INTERNAL_API_URL: string;

  // Auth (dev only)
  SERVICE_TOKEN: string | null;

  // Features
  CHAT_WIDGET_KEY: string | null;

  // Build info
  BUILD_ID: string | null;
}

/**
 * Get raw environment variable value
 */
function getEnvVar(key: string, fallback?: string): string | undefined {
  if (typeof window !== 'undefined') {
    // Client-side: only NEXT_PUBLIC_ vars are available
    return (process.env as Record<string, string | undefined>)[key] ?? fallback;
  }
  // Server-side: all vars available
  return process.env[key] ?? fallback;
}

/**
 * Get required environment variable or throw
 */
function requireEnvVar(key: string): string {
  const value = getEnvVar(key);
  if (!value) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
  return value;
}

/**
 * Validate and parse environment configuration
 */
function parseEnv(): EnvConfig {
  const nodeEnv = (getEnvVar('NODE_ENV', 'development') as Environment) || 'development';
  const isDevelopment = nodeEnv === 'development';
  const isProduction = nodeEnv === 'production';
  const isTest = nodeEnv === 'test';

  // API URL: required in production, has sensible defaults in dev
  const apiUrl = getEnvVar('NEXT_PUBLIC_API_URL', isDevelopment ? 'http://localhost:8000' : '');
  const internalApiUrl = getEnvVar('INTERNAL_API_URL', apiUrl);

  if (isProduction && !apiUrl) {
    console.error('NEXT_PUBLIC_API_URL is required in production');
  }

  // Service token: only available in development
  const serviceToken = isDevelopment ? getEnvVar('NEXT_PUBLIC_SERVICE_TOKEN') ?? null : null;

  // Optional feature configs
  const chatWidgetKey = getEnvVar('NEXT_PUBLIC_CHAT_WIDGET_KEY') ?? null;
  const buildId = getEnvVar('NEXT_PUBLIC_BUILD_ID') ?? null;

  return {
    NODE_ENV: nodeEnv,
    IS_DEVELOPMENT: isDevelopment,
    IS_PRODUCTION: isProduction,
    IS_TEST: isTest,
    API_URL: apiUrl || '',
    INTERNAL_API_URL: internalApiUrl || '',
    SERVICE_TOKEN: serviceToken,
    CHAT_WIDGET_KEY: chatWidgetKey,
    BUILD_ID: buildId,
  };
}

/**
 * Singleton environment configuration
 */
let envConfig: EnvConfig | null = null;

export function getEnv(): EnvConfig {
  if (!envConfig) {
    envConfig = parseEnv();
  }
  return envConfig;
}

// Convenience exports for common checks
export const env = {
  get config() {
    return getEnv();
  },

  get isDevelopment() {
    return getEnv().IS_DEVELOPMENT;
  },

  get isProduction() {
    return getEnv().IS_PRODUCTION;
  },

  get isTest() {
    return getEnv().IS_TEST;
  },

  get apiUrl() {
    return getEnv().API_URL;
  },

  get internalApiUrl() {
    return getEnv().INTERNAL_API_URL;
  },

  /**
   * Get service token (dev only)
   * Returns null in production for safety
   */
  get serviceToken() {
    return getEnv().SERVICE_TOKEN;
  },

  /**
   * Check if we're running on the client side
   */
  get isClient() {
    return typeof window !== 'undefined';
  },

  /**
   * Check if we're running on the server side
   */
  get isServer() {
    return typeof window === 'undefined';
  },
};

/**
 * Validate that all required environment variables are set.
 * Call this at app startup to fail fast if config is invalid.
 */
export function validateEnv(): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  const config = getEnv();
  const rawServiceToken = getEnvVar('NEXT_PUBLIC_SERVICE_TOKEN');

  if (config.IS_PRODUCTION) {
    if (!config.API_URL) {
      errors.push('NEXT_PUBLIC_API_URL is required in production');
    }

    if (rawServiceToken) {
      errors.push('NEXT_PUBLIC_SERVICE_TOKEN should not be set in production');
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

export default env;
