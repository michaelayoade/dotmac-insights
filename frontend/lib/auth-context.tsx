'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { ApiError, clearAuthToken, fetchApi, onAuthError } from './api';

// Scope definitions - maps to backend RBAC scopes
// Keep in sync with backend scopes from Require() calls in app/api/
export type Scope =
  // Wildcard
  | '*'
  // Admin scopes
  | 'admin:read'
  | 'admin:write'
  | 'admin:users:read'
  | 'admin:users:write'
  | 'admin:roles:read'
  | 'admin:roles:write'
  | 'admin:tokens:read'
  | 'admin:tokens:write'
  // Analytics & Explorer
  | 'analytics:read'
  | 'explorer:read'
  // Sync scopes
  | 'sync:read'
  | 'sync:write'
  | 'sync:splynx:read'
  | 'sync:splynx:write'
  | 'sync:erpnext:write'
  | 'sync:chatwoot:write'
  // Customer & Contact scopes
  | 'customers:read'
  | 'customers:write'
  | 'contacts:read'
  | 'contacts:write'
  // CRM scopes
  | 'crm:read'
  | 'crm:write'
  | 'crm:admin'
  // HR scopes
  | 'hr:read'
  | 'hr:write'
  | 'hr:admin'
  // Fleet scopes
  | 'fleet:read'
  | 'fleet:write'
  // Support scopes
  | 'support:read'
  | 'support:write'
  | 'support:admin'
  | 'support:automation:read'
  | 'support:automation:write'
  | 'support:csat:read'
  | 'support:csat:write'
  | 'support:kb:read'
  | 'support:kb:write'
  | 'support:sla:read'
  | 'support:sla:write'
  // Tickets scopes
  | 'tickets:read'
  | 'tickets:write'
  // Inbox scopes
  | 'inbox:read'
  | 'inbox:write'
  // Accounting scopes
  | 'accounting:read'
  | 'accounting:write'
  // Assets scopes
  | 'assets:read'
  | 'assets:write'
  // Books/Finance scopes
  | 'books:read'
  | 'books:write'
  | 'books:approve'
  | 'books:admin'
  | 'books:close'
  | 'billing:write'
  // Expenses scopes
  | 'expenses:read'
  | 'expenses:write'
  // Field Service scopes
  | 'field-service:read'
  | 'field-service:write'
  | 'field-service:dispatch'
  | 'field-service:admin'
  | 'field-service:mobile'
  // Purchasing scopes
  | 'purchasing:read'
  | 'purchasing:write'
  // Projects scopes
  | 'projects:read'
  | 'projects:write'
  // Reports scopes
  | 'reports:read'
  | 'reports:write'
  // Payments & Banking scopes
  | 'payments:read'
  | 'payments:write'
  | 'openbanking:read'
  | 'openbanking:write'
  | 'gateway:read'
  | 'gateway:write'
  // Inventory scopes
  | 'inventory:read'
  | 'inventory:write'
  | 'inventory:approve'
  // Sales scopes
  | 'sales:read'
  | 'sales:write'
  // Settings scopes
  | 'settings:read'
  | 'settings:write'
  | 'settings:audit_view'
  | 'settings:test'
  // Performance Management scopes
  | 'performance:read'
  | 'performance:write'
  | 'performance:admin'
  | 'performance:review'
  | 'performance:self'
  | 'performance:team';

/**
 * Human-readable display names for permission scopes.
 * Used in UI to show friendly names instead of raw scope strings.
 */
export const SCOPE_DISPLAY_NAMES: Record<string, string> = {
  // Wildcard
  '*': 'Full Access',
  // Admin
  'admin:read': 'View Admin',
  'admin:write': 'Manage Admin',
  'admin:users:read': 'View Users',
  'admin:users:write': 'Manage Users',
  'admin:roles:read': 'View Roles',
  'admin:roles:write': 'Manage Roles',
  'admin:tokens:read': 'View Service Tokens',
  'admin:tokens:write': 'Manage Service Tokens',
  // Analytics & Explorer
  'analytics:read': 'View Analytics',
  'explorer:read': 'Data Explorer',
  // Sync
  'sync:read': 'View Sync Status',
  'sync:write': 'Manage Sync',
  'sync:splynx:read': 'View Splynx Sync',
  'sync:splynx:write': 'Manage Splynx Sync',
  'sync:erpnext:write': 'Manage ERPNext Sync',
  'sync:chatwoot:write': 'Manage Chatwoot Sync',
  // Customers & Contacts
  'customers:read': 'View Customers',
  'customers:write': 'Manage Customers',
  'contacts:read': 'View Contacts',
  'contacts:write': 'Manage Contacts',
  // CRM
  'crm:read': 'View CRM',
  'crm:write': 'Manage CRM',
  'crm:admin': 'Administer CRM',
  // HR
  'hr:read': 'View HR',
  'hr:write': 'Manage HR',
  'hr:admin': 'Administer HR',
  // Fleet
  'fleet:read': 'View Fleet',
  'fleet:write': 'Manage Fleet',
  // Support
  'support:read': 'View Support',
  'support:write': 'Manage Support',
  'support:admin': 'Administer Support',
  'support:automation:read': 'View Support Automation',
  'support:automation:write': 'Manage Support Automation',
  'support:csat:read': 'View CSAT',
  'support:csat:write': 'Manage CSAT',
  'support:kb:read': 'View Knowledge Base',
  'support:kb:write': 'Manage Knowledge Base',
  'support:sla:read': 'View SLA',
  'support:sla:write': 'Manage SLA',
  // Tickets
  'tickets:read': 'View Tickets',
  'tickets:write': 'Manage Tickets',
  // Inbox
  'inbox:read': 'View Inbox',
  'inbox:write': 'Manage Inbox',
  // Accounting
  'accounting:read': 'View Accounting',
  'accounting:write': 'Manage Accounting',
  // Assets
  'assets:read': 'View Assets',
  'assets:write': 'Manage Assets',
  // Books
  'books:read': 'View Books',
  'books:write': 'Manage Books',
  'books:approve': 'Approve Transactions',
  'books:admin': 'Administer Books',
  'books:close': 'Close Periods',
  'billing:write': 'Manage Billing',
  // Expenses
  'expenses:read': 'View Expenses',
  'expenses:write': 'Manage Expenses',
  // Field Service
  'field-service:read': 'View Field Service',
  'field-service:write': 'Manage Field Service',
  'field-service:dispatch': 'Dispatch Orders',
  'field-service:admin': 'Administer Field Service',
  'field-service:mobile': 'Field Service Mobile',
  // Purchasing
  'purchasing:read': 'View Purchasing',
  'purchasing:write': 'Manage Purchasing',
  // Projects
  'projects:read': 'View Projects',
  'projects:write': 'Manage Projects',
  // Reports
  'reports:read': 'View Reports',
  'reports:write': 'Manage Reports',
  // Payments & Banking
  'payments:read': 'View Payments',
  'payments:write': 'Manage Payments',
  'openbanking:read': 'View Open Banking',
  'openbanking:write': 'Manage Open Banking',
  'gateway:read': 'View Payment Gateway',
  'gateway:write': 'Manage Payment Gateway',
  // Inventory
  'inventory:read': 'View Inventory',
  'inventory:write': 'Manage Inventory',
  'inventory:approve': 'Approve Inventory',
  // Sales
  'sales:read': 'View Sales',
  'sales:write': 'Manage Sales',
  // Settings
  'settings:read': 'View Settings',
  'settings:write': 'Manage Settings',
  'settings:audit_view': 'View Audit Logs',
  'settings:test': 'Test Settings',
  // Performance Management
  'performance:read': 'View Performance',
  'performance:write': 'Manage Performance',
  'performance:admin': 'Administer Performance',
  'performance:review': 'Review Performance',
  'performance:self': 'View Own Performance',
  'performance:team': 'View Team Performance',
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
      const status = apiError?.status ?? 0;

      // 401: Not authenticated - clear auth state
      if (status === 401) {
        setState({
          isAuthenticated: false,
          isLoading: false,
          scopes: [],
          error: null,
        });
        return;
      }

      // 5xx or network error: Keep existing auth state, just show error
      // Don't hard-logout on transient failures
      if (status === 0 || status >= 500) {
        setState(prev => ({
          ...prev,
          isLoading: false,
          error: 'Unable to verify session. Please try again.',
        }));
        return;
      }

      // Other errors (403, 4xx): Clear auth as session may be invalid
      setState({
        isAuthenticated: false,
        isLoading: false,
        scopes: [],
        error: apiError?.message || 'Session verification failed',
      });
    }
  }, []);

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
    // Global wildcard grants all permissions
    if (state.scopes.includes('*' as Scope)) return true;

    // Check for exact match
    if (state.scopes.includes(scope)) return true;

    // Check for wildcard matches at any level
    // e.g., 'admin:*' matches 'admin:users:read', 'admin:roles:write', etc.
    // e.g., 'support:*' matches 'support:sla:read', 'support:kb:write', etc.
    for (const userScope of state.scopes) {
      if (userScope.endsWith(':*')) {
        const prefix = userScope.slice(0, -1); // Remove the '*', keep the ':'
        if (scope.startsWith(prefix)) {
          return true;
        }
      }
    }

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
    missingScope: !isLoading && !hasAccess,
  };
}
