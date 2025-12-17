import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';

/**
 * Feature flag definitions
 * Add new features here with their default values
 */
export type FeatureFlag =
  | 'dark_mode'
  | 'new_dashboard'
  | 'ai_insights'
  | 'bulk_operations'
  | 'advanced_reports'
  | 'beta_features'
  | 'experimental_ui';

type FeatureFlags = Record<FeatureFlag, boolean>;

const DEFAULT_FLAGS: FeatureFlags = {
  dark_mode: true,
  new_dashboard: false,
  ai_insights: false,
  bulk_operations: true,
  advanced_reports: false,
  beta_features: false,
  experimental_ui: false,
};

interface FeatureGateContextValue {
  flags: FeatureFlags;
  isEnabled: (flag: FeatureFlag) => boolean;
  isDisabled: (flag: FeatureFlag) => boolean;
  enableFlag: (flag: FeatureFlag) => void;
  disableFlag: (flag: FeatureFlag) => void;
  toggleFlag: (flag: FeatureFlag) => void;
  setFlags: (flags: Partial<FeatureFlags>) => void;
  resetFlags: () => void;
}

const FeatureGateContext = createContext<FeatureGateContextValue | null>(null);

const STORAGE_KEY = 'dotmac_feature_flags';

/**
 * Load flags from localStorage, merging with defaults
 */
function loadFlags(): FeatureFlags {
  if (typeof window === 'undefined') return DEFAULT_FLAGS;

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored) as Partial<FeatureFlags>;
      return { ...DEFAULT_FLAGS, ...parsed };
    }
  } catch {
    // Invalid JSON, use defaults
  }

  return DEFAULT_FLAGS;
}

/**
 * Save flags to localStorage
 */
function saveFlags(flags: FeatureFlags): void {
  if (typeof window === 'undefined') return;

  try {
    // Only save flags that differ from defaults
    const diff: Partial<FeatureFlags> = {};
    for (const key of Object.keys(flags) as FeatureFlag[]) {
      if (flags[key] !== DEFAULT_FLAGS[key]) {
        diff[key] = flags[key];
      }
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(diff));
  } catch {
    // Storage full or unavailable
  }
}

/**
 * Provider component for feature flags
 *
 * @example
 * <FeatureGateProvider>
 *   <App />
 * </FeatureGateProvider>
 */
export function FeatureGateProvider({ children }: { children: ReactNode }) {
  const [flags, setFlagsState] = useState<FeatureFlags>(DEFAULT_FLAGS);

  // Load from storage on mount
  useEffect(() => {
    setFlagsState(loadFlags());
  }, []);

  // Save to storage when flags change
  useEffect(() => {
    saveFlags(flags);
  }, [flags]);

  const isEnabled = useCallback((flag: FeatureFlag) => flags[flag] === true, [flags]);
  const isDisabled = useCallback((flag: FeatureFlag) => flags[flag] === false, [flags]);

  const enableFlag = useCallback((flag: FeatureFlag) => {
    setFlagsState((prev) => ({ ...prev, [flag]: true }));
  }, []);

  const disableFlag = useCallback((flag: FeatureFlag) => {
    setFlagsState((prev) => ({ ...prev, [flag]: false }));
  }, []);

  const toggleFlag = useCallback((flag: FeatureFlag) => {
    setFlagsState((prev) => ({ ...prev, [flag]: !prev[flag] }));
  }, []);

  const setFlags = useCallback((newFlags: Partial<FeatureFlags>) => {
    setFlagsState((prev) => ({ ...prev, ...newFlags }));
  }, []);

  const resetFlags = useCallback(() => {
    setFlagsState(DEFAULT_FLAGS);
    if (typeof window !== 'undefined') {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  return (
    <FeatureGateContext.Provider
      value={{
        flags,
        isEnabled,
        isDisabled,
        enableFlag,
        disableFlag,
        toggleFlag,
        setFlags,
        resetFlags,
      }}
    >
      {children}
    </FeatureGateContext.Provider>
  );
}

/**
 * Hook to access feature flags
 *
 * @example
 * const { isEnabled, toggleFlag } = useFeatureGate();
 *
 * if (isEnabled('new_dashboard')) {
 *   return <NewDashboard />;
 * }
 */
export function useFeatureGate(): FeatureGateContextValue {
  const context = useContext(FeatureGateContext);

  // If no provider, return a standalone implementation
  if (!context) {
    const flags = typeof window !== 'undefined' ? loadFlags() : DEFAULT_FLAGS;

    return {
      flags,
      isEnabled: (flag: FeatureFlag) => flags[flag] === true,
      isDisabled: (flag: FeatureFlag) => flags[flag] === false,
      enableFlag: () => console.warn('FeatureGateProvider not found'),
      disableFlag: () => console.warn('FeatureGateProvider not found'),
      toggleFlag: () => console.warn('FeatureGateProvider not found'),
      setFlags: () => console.warn('FeatureGateProvider not found'),
      resetFlags: () => console.warn('FeatureGateProvider not found'),
    };
  }

  return context;
}

/**
 * Hook to check if a specific feature is enabled
 *
 * @example
 * const isNewDashboardEnabled = useFeatureFlag('new_dashboard');
 */
export function useFeatureFlag(flag: FeatureFlag): boolean {
  const { isEnabled } = useFeatureGate();
  return isEnabled(flag);
}

/**
 * Component that conditionally renders children based on feature flag
 *
 * @example
 * <FeatureGate flag="new_dashboard">
 *   <NewDashboard />
 * </FeatureGate>
 *
 * <FeatureGate flag="new_dashboard" fallback={<OldDashboard />}>
 *   <NewDashboard />
 * </FeatureGate>
 */
export function FeatureGate({
  flag,
  children,
  fallback = null,
}: {
  flag: FeatureFlag;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const isEnabled = useFeatureFlag(flag);
  return isEnabled ? <>{children}</> : <>{fallback}</>;
}

export default useFeatureGate;
