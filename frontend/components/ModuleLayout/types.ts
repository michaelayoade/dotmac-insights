/**
 * ModuleLayout Types
 *
 * Shared type definitions for ModuleLayout components.
 */

import type { LucideIcon } from 'lucide-react';
import type { AccentColor } from '@/lib/config/colors';

// =============================================================================
// NAVIGATION TYPES
// =============================================================================

export interface NavItem {
  name: string;
  href: string;
  description?: string;
}

export interface NavSection {
  key: string;
  label: string;
  description: string;
  icon: LucideIcon;
  items: NavItem[];
}

export type QuickLinkColor =
  | 'amber-400'
  | 'blue-400'
  | 'coral-alert'
  | 'cyan-400'
  | 'emerald-400'
  | 'indigo-400'
  | 'orange-400'
  | 'rose-400'
  | 'sky-400'
  | 'teal-400'
  | 'violet-400';

export type WorkflowStepColor =
  | 'amber'
  | 'blue'
  | 'cyan'
  | 'emerald'
  | 'indigo'
  | 'orange'
  | 'rose'
  | 'sky'
  | 'teal'
  | 'violet';

export interface QuickLink {
  label: string;
  href: string;
  icon: LucideIcon;
  color: QuickLinkColor;
}

// =============================================================================
// WORKFLOW TYPES
// =============================================================================

export interface WorkflowPhase {
  key: string;
  label: string;
  description?: string;
}

export interface WorkflowStep {
  label: string;
  color: WorkflowStepColor;
}

// =============================================================================
// COMPONENT PROPS
// =============================================================================

export interface ModuleLayoutProps {
  /** Module display name (e.g., "Dotmac People") */
  moduleName: string;
  /** Subtitle shown below module name (e.g., "HR & Workforce") */
  moduleSubtitle: string;
  /** Sidebar title (e.g., "Human Resources") */
  sidebarTitle: string;
  /** Sidebar description */
  sidebarDescription: string;
  /** Base route for the module (e.g., "/hr") */
  baseRoute: string;
  /** Accent color theme */
  accentColor: AccentColor;
  /** Module icon */
  icon: LucideIcon;
  /** Navigation sections */
  sections: NavSection[];
  /** Optional quick links grid */
  quickLinks?: QuickLink[];
  /** Optional workflow phases indicator */
  workflowPhases?: WorkflowPhase[];
  /** Function to determine current workflow phase from section key */
  getWorkflowPhase?: (sectionKey: string | null) => string;
  /** Optional workflow steps guide */
  workflowSteps?: WorkflowStep[];
  /** Optional header content (e.g., live metrics) */
  headerContent?: React.ReactNode;
  /** Children content */
  children: React.ReactNode;
}

// =============================================================================
// INTERNAL TYPES
// =============================================================================

/** Sidebar color configuration from getSidebarColors */
export interface SidebarColors {
  iconBg: string;
  iconText: string;
  activeBg: string;
  activeBorder: string;
  activeText: string;
  activeItemBg: string;
  activeItemText: string;
  activeDescText: string;
}
