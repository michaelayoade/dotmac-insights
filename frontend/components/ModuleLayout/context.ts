'use client';

import { createContext, useContext } from 'react';
import type { SidebarColors, NavSection, WorkflowPhase } from './types';

// =============================================================================
// CONTEXT TYPE
// =============================================================================

export interface ModuleLayoutContextValue {
  /** Sidebar color configuration */
  colors: SidebarColors;
  /** Base route for the module */
  baseRoute: string;
  /** Current pathname */
  pathname: string;
  /** Currently active section key */
  activeSection: string | null;
  /** Currently active href */
  activeHref: string;
  /** Current workflow phase key */
  currentPhase: string;
  /** Navigation sections */
  sections: NavSection[];
  /** Open sections state */
  openSections: Record<string, boolean>;
  /** Toggle a section's open state */
  toggleSection: (key: string) => void;
  /** Workflow phases */
  workflowPhases?: WorkflowPhase[];
  /** Get workflow phase for a section */
  getWorkflowPhase?: (sectionKey: string | null) => string;
  /** Toggle theme */
  toggleTheme: () => void;
  /** Is dark mode active */
  isDarkMode: boolean;
  /** Is user authenticated */
  isAuthenticated: boolean;
  /** Logout function */
  logout: () => void;
  /** Open command palette */
  openCommandPalette: () => void;
}

// =============================================================================
// CONTEXT
// =============================================================================

export const ModuleLayoutContext = createContext<ModuleLayoutContextValue | null>(null);

/**
 * Hook to access ModuleLayout context
 * Must be used within a ModuleLayout component
 */
export function useModuleLayoutContext(): ModuleLayoutContextValue {
  const context = useContext(ModuleLayoutContext);
  if (!context) {
    throw new Error('useModuleLayoutContext must be used within a ModuleLayout');
  }
  return context;
}
