'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode, useRef } from 'react';
import { ApiError, clearAuthToken, fetchApi, onAuthError, setAuthToken } from './api';

// Scope definitions - maps to backend RBAC scopes
export type Scope =
  | 'customers:read'
  | 'customers:write'
  | 'contacts:read'
  | 'contacts:write'
  | 'analytics:read'
  | 'sync:read'
  | 'sync:write'
  | 'explore:read'
  | 'admin:read'
  | 'admin:write'
  | 'hr:read'
  | 'hr:write'
  | 'support:read'
  | 'support:write'
  | 'inbox:read'
  | 'inbox:write'
  | 'accounting:read'
  | 'accounting:write'
  | 'purchasing:read'
  | 'purchasing:write'
  | 'payments:read'
  | 'payments:write'
  | 'openbanking:read'
  | 'openbanking:write'
  | 'gateway:read'
  | 'gateway:write'
  | 'inventory:read'
  | 'inventory:write'
  | 'sales:read'
  | 'sales:write'
  | '*';

/**
 * Human-readable display names for permission scopes.
 * Used in UI to show friendly names instead of raw scope strings.
 */
export const SCOPE_DISPLAY_NAMES: Record<string, string> = {
  'customers:read': 'View Customers',
  'customers:write': 'Manage Customers',
  'contacts:read': 'View Contacts',
  'contacts:write': 'Manage Contacts',
  'analytics:read': 'View Analytics',
  'sync:read': 'View Sync Status',
  'sync:write': 'Manage Sync',
  'explore:read': 'Data Explorer',
  'admin:read': 'View Admin',
  'admin:write': 'Manage Admin',
  'hr:read': 'View HR',
  'hr:write': 'Manage HR',
  'support:read': 'View Support',
  'support:write': 'Manage Support',
  'inbox:read': 'View Inbox',
  'inbox:write': 'Manage Inbox',
  'accounting:read': 'View Accounting',
  'accounting:write': 'Manage Accounting',
  'purchasing:read': 'View Purchasing',
  'purchasing:write': 'Manage Purchasing',
  'payments:read': 'View Payments',
  'payments:write': 'Manage Payments',
  'openbanking:read': 'View Open Banking',
  'openbanking:write': 'Manage Open Banking',
  'gateway:read': 'View Payment Gateway',
  'gateway:write': 'Manage Payment Gateway',
  'inventory:read': 'View Inventory',
  'inventory:write': 'Manage Inventory',
  'sales:read': 'View Sales',
  'sales:write': 'Manage Sales',
  '*': 'Full Access',
};

/**
 * Get human-readable display name for a scope
 */
export function getScopeDisplayName(scope: string): string {
  return SCOPE_DISPLAY_NAMES[scope] || scope.replace(':', ': ').replace(/_/g, ' ');
}

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  scopes: Scope[];
  error: string | null;
}

interface AuthContextValue extends AuthState {
  hasScope: (scope: Scope) => boolean;
  hasAnyScope: (scopes: Scope[]) => boolean;
  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

interface MeResponse {
  permissions: string[];
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    scopes: [],
    error: null,
  });
  const devToken = process.env.NEXT_PUBLIC_DEV_TOKEN || '';
  const canUseDevToken = devToken.length > 0 && process.env.NODE_ENV !== 'production';
  const devAuthAttempted = useRef(false);

  const checkAuth = useCallback(async () => {
    if (typeof window === 'undefined') {
      setState(prev => ({ ...prev, isLoading: false }));
      return;
    }

    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const me = await fetchApi<MeResponse>('/admin/me');
      const scopes = (me.permissions || []) as Scope[];
      setState({
        isAuthenticated: true,
        isLoading: false,
        scopes,
        error: null,
      });
    } catch (error) {
      const apiError = error instanceof ApiError ? error : null;
      const isAuthError = apiError?.status === 401;
      if (isAuthError && canUseDevToken && !devAuthAttempted.current) {
        devAuthAttempted.current = true;
        try {
          await setAuthToken(devToken);
          const me = await fetchApi<MeResponse>('/admin/me');
          const scopes = (me.permissions || []) as Scope[];
          setState({
            isAuthenticated: true,
            isLoading: false,
            scopes,
            error: null,
          });
          return;
        } catch (authError) {
          const message = authError instanceof Error ? authError.message : 'Dev auto-login failed';
          setState({
            isAuthenticated: false,
            isLoading: false,
            scopes: [],
            error: message,
          });
          return;
        }
      }
      setState({
        isAuthenticated: false,
        isLoading: false,
        scopes: [],
        error: isAuthError ? null : 'Unable to verify session',
      });
    }
  }, [canUseDevToken, devToken]);

  const login = useCallback(async (token: string) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    try {
      await setAuthToken(token);
      await checkAuth();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Authentication failed';
      setState({
        isAuthenticated: false,
        isLoading: false,
        scopes: [],
        error: message,
      });
    }
  }, [checkAuth]);

  const logout = useCallback(async () => {
    await clearAuthToken();
    setState({
      isAuthenticated: false,
      isLoading: false,
      scopes: [],
      error: null,
    });
  }, []);

  const hasScope = useCallback((scope: Scope): boolean => {
    // Wildcard grants all permissions
    if (state.scopes.includes('*' as Scope)) return true;
    // Check for exact match
    if (state.scopes.includes(scope)) return true;
    // Check for module wildcard (e.g., 'admin:*' matches 'admin:read')
    const [module] = scope.split(':');
    if (state.scopes.includes(`${module}:*` as Scope)) return true;
    return false;
  }, [state.scopes]);

  const hasAnyScope = useCallback((scopes: Scope[]): boolean => {
    return scopes.some(scope => hasScope(scope));
  }, [hasScope]);

  // Initial auth check
  useEffect(() => {
    void checkAuth();
  }, [checkAuth]);

  // Listen for auth errors
  useEffect(() => {
    const unsubscribe = onAuthError((event) => {
      if (event === 'unauthorized' || event === 'token_expired') {
        void logout();
      }
    });
    return unsubscribe;
  }, [logout]);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        hasScope,
        hasAnyScope,
        login,
        logout,
        checkAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Hook for protecting routes/components by scope
export function useRequireScope(scope: Scope | Scope[]) {
  const { isAuthenticated, isLoading, scopes, hasScope, hasAnyScope } = useAuth();

  const requiredScopes = Array.isArray(scope) ? scope : [scope];

  // Check if user has any of the required scopes or wildcard access
  const hasAccess = isLoading
    ? false
    : !isAuthenticated
    ? false
    : scopes.includes('*' as Scope)
    ? true
    : hasAnyScope(requiredScopes);

  return {
    isLoading,
    isAuthenticated,
    hasAccess,
    missingScope: !isLoading && isAuthenticated && !hasAccess,
  };
}
