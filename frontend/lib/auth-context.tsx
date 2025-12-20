'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { hasAuthToken, clearAuthToken, setAuthToken, onAuthError } from './api';

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
  | '*';

const ALL_SCOPES: Scope[] = [
  'customers:read',
  'customers:write',
  'contacts:read',
  'contacts:write',
  'analytics:read',
  'sync:read',
  'sync:write',
  'explore:read',
  'admin:read',
  'admin:write',
  'hr:read',
  'hr:write',
  'support:read',
  'support:write',
  'inbox:read',
  'inbox:write',
  'accounting:read',
  'accounting:write',
  'purchasing:read',
  'purchasing:write',
];

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  scopes: Scope[];
  error: string | null;
}

interface AuthContextValue extends AuthState {
  hasScope: (scope: Scope) => boolean;
  hasAnyScope: (scopes: Scope[]) => boolean;
  login: (token: string, scopes?: Scope[]) => void;
  logout: () => void;
  checkAuth: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// Decode JWT to extract scopes (without verification - that's done server-side)
function decodeJwtPayload(token: string): { scopes?: string[]; exp?: number } | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload;
  } catch {
    return null;
  }
}

// Check if token is expired
function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return false;
  return Date.now() >= payload.exp * 1000;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    scopes: [],
    error: null,
  });

  const checkAuth = useCallback(() => {
    if (typeof window === 'undefined') {
      setState(prev => ({ ...prev, isLoading: false }));
      return;
    }

    const token = localStorage.getItem('dotmac_access_token');

    if (!token) {
      setState({
        isAuthenticated: false,
        isLoading: false,
        scopes: [],
        error: null,
      });
      return;
    }

    // Check token expiration
    if (isTokenExpired(token)) {
      clearAuthToken();
      setState({
        isAuthenticated: false,
        isLoading: false,
        scopes: [],
        error: 'Session expired',
      });
      return;
    }

    // Decode token to get scopes
    const payload = decodeJwtPayload(token);
    const scopes = (payload?.scopes || []) as Scope[];

    setState({
      isAuthenticated: true,
      isLoading: false,
      scopes,
      error: null,
    });
  }, []);

  const login = useCallback((token: string, scopes?: Scope[]) => {
    setAuthToken(token);

    // If scopes not provided, try to decode from token
    const tokenScopes = scopes || (decodeJwtPayload(token)?.scopes as Scope[]) || [];

    setState({
      isAuthenticated: true,
      isLoading: false,
      scopes: tokenScopes,
      error: null,
    });
  }, []);

  const logout = useCallback(() => {
    clearAuthToken();
    setState({
      isAuthenticated: false,
      isLoading: false,
      scopes: [],
      error: null,
    });
  }, []);

  const hasScope = useCallback((scope: Scope): boolean => {
    return state.scopes.includes(scope);
  }, [state.scopes]);

  const hasAnyScope = useCallback((scopes: Scope[]): boolean => {
    return scopes.some(scope => state.scopes.includes(scope));
  }, [state.scopes]);

  // Initial auth check
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Listen for auth errors
  useEffect(() => {
    const unsubscribe = onAuthError((event) => {
      if (event === 'unauthorized' || event === 'token_expired') {
        logout();
      }
    });
    return unsubscribe;
  }, [logout]);

  // Listen for storage changes (cross-tab sync)
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'dotmac_access_token') {
        checkAuth();
      }
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [checkAuth]);

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
