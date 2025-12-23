/**
 * ModuleLayout Utilities
 *
 * Helper functions for navigation and path matching.
 */

import type { NavSection, QuickLinkColor, WorkflowStepColor } from './types';

/**
 * Check if a path is active (exact match or starts with href)
 */
export function isActivePath(pathname: string, href: string, baseRoute: string): boolean {
  if (href === baseRoute) return pathname === baseRoute;
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Get the key of the currently active section
 */
export function getActiveSection(
  pathname: string,
  sections: NavSection[],
  baseRoute: string
): string | null {
  for (const section of sections) {
    if (section.items.some((item) => isActivePath(pathname, item.href, baseRoute))) {
      return section.key;
    }
  }
  return null;
}

/**
 * Get the href of the currently active item
 */
export function getActiveHref(
  pathname: string,
  sections: NavSection[],
  baseRoute: string
): string {
  for (const section of sections) {
    for (const item of section.items) {
      if (isActivePath(pathname, item.href, baseRoute)) return item.href;
    }
  }
  return '';
}

// =============================================================================
// COLOR HELPERS
// =============================================================================

const QUICK_LINK_COLOR_CLASSES: Record<QuickLinkColor, string> = {
  'amber-400': 'text-amber-400',
  'blue-400': 'text-blue-400',
  'coral-alert': 'text-coral-alert',
  'cyan-400': 'text-cyan-400',
  'emerald-400': 'text-emerald-400',
  'indigo-400': 'text-indigo-400',
  'orange-400': 'text-orange-400',
  'rose-400': 'text-rose-400',
  'sky-400': 'text-sky-400',
  'teal-400': 'text-teal-400',
  'violet-400': 'text-violet-400',
};

const WORKFLOW_STEP_CLASSES: Record<WorkflowStepColor, { bg: string; text: string }> = {
  amber: { bg: 'bg-amber-500/20', text: 'text-amber-400' },
  blue: { bg: 'bg-blue-500/20', text: 'text-blue-400' },
  cyan: { bg: 'bg-cyan-500/20', text: 'text-cyan-400' },
  emerald: { bg: 'bg-emerald-500/20', text: 'text-emerald-400' },
  indigo: { bg: 'bg-indigo-500/20', text: 'text-indigo-400' },
  orange: { bg: 'bg-orange-500/20', text: 'text-orange-400' },
  rose: { bg: 'bg-rose-500/20', text: 'text-rose-400' },
  sky: { bg: 'bg-sky-500/20', text: 'text-sky-400' },
  teal: { bg: 'bg-teal-500/20', text: 'text-teal-400' },
  violet: { bg: 'bg-violet-500/20', text: 'text-violet-400' },
};

export function getQuickLinkColorClass(color: QuickLinkColor): string {
  return QUICK_LINK_COLOR_CLASSES[color];
}

export function getWorkflowStepClasses(color: WorkflowStepColor): { bg: string; text: string } {
  return WORKFLOW_STEP_CLASSES[color];
}
