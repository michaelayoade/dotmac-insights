/**
 * DESIGN TOKENS - Single Source of Truth
 *
 * This file defines all design tokens for the Dotmac Insights application.
 * All colors, spacing, and variant definitions should reference these tokens.
 *
 * Token Hierarchy:
 * 1. CSS Variables (globals.css) - Runtime theming (light/dark)
 * 2. This file - Semantic mappings and Tailwind references
 * 3. Tailwind config - References CSS variables from this file
 * 4. Components - Use Tailwind classes that reference these tokens
 */

// =============================================================================
// VARIANT VOCABULARY (Locked)
// =============================================================================

/**
 * Standard variant types used across all components.
 * DO NOT add new variants without updating all components.
 */
export type Variant = 'default' | 'success' | 'warning' | 'danger' | 'info';

/**
 * Semantic color mapping for variants.
 * Maps variant names to Tailwind color references.
 */
export const VARIANT_COLORS = {
  default: {
    bg: 'bg-slate-elevated',
    bgSubtle: 'bg-slate-elevated/50',
    text: 'text-slate-muted',
    border: 'border-slate-border',
    icon: 'text-slate-muted',
  },
  success: {
    bg: 'bg-teal-electric/15',
    bgSubtle: 'bg-teal-electric/10',
    text: 'text-teal-electric',
    border: 'border-teal-electric/30',
    icon: 'text-teal-electric',
  },
  warning: {
    bg: 'bg-amber-warn/15',
    bgSubtle: 'bg-amber-warn/10',
    text: 'text-amber-warn',
    border: 'border-amber-warn/30',
    icon: 'text-amber-warn',
  },
  danger: {
    bg: 'bg-coral-alert/15',
    bgSubtle: 'bg-coral-alert/10',
    text: 'text-coral-alert',
    border: 'border-coral-alert/30',
    icon: 'text-coral-alert',
  },
  info: {
    bg: 'bg-blue-info/15',
    bgSubtle: 'bg-blue-info/10',
    text: 'text-blue-info',
    border: 'border-blue-info/30',
    icon: 'text-blue-info',
  },
} as const;

// =============================================================================
// SPACING SCALE (8px Grid)
// =============================================================================

/**
 * Spacing scale based on 8px grid system.
 * Use these values for consistent spacing throughout the app.
 *
 * Exceptions allowed:
 * - 2px for fine adjustments (borders, outlines)
 * - 4px for compact elements (badges, small gaps)
 */
export const SPACING = {
  0: '0px',
  0.5: '2px',   // Exception: fine adjustments
  1: '4px',     // Exception: compact elements
  2: '8px',     // Base unit
  3: '12px',    // 1.5x base (allowed for badges)
  4: '16px',    // 2x base - standard gap
  5: '20px',    // 2.5x base
  6: '24px',    // 3x base - section gap
  8: '32px',    // 4x base - large gap
  10: '40px',   // 5x base
  12: '48px',   // 6x base - page padding
  16: '64px',   // 8x base - major sections
} as const;

/**
 * Standard gap sizes for layouts
 */
export const LAYOUT_GAPS = {
  xs: 'gap-1',   // 4px - compact lists
  sm: 'gap-2',   // 8px - tight spacing
  md: 'gap-4',   // 16px - standard spacing
  lg: 'gap-6',   // 24px - section spacing
  xl: 'gap-8',   // 32px - major sections
} as const;

/**
 * Standard padding sizes
 */
export const LAYOUT_PADDING = {
  card: 'p-5',           // 20px - card content
  cardLg: 'p-6',         // 24px - large cards
  section: 'p-4 lg:p-6', // Responsive section padding
  page: 'p-4 lg:p-8',    // Responsive page padding
} as const;

// =============================================================================
// CHART PALETTE (Theme-Aware)
// =============================================================================

/**
 * Chart colors that work in both light and dark themes.
 * These are CSS variable references for runtime theme switching.
 *
 * Usage in Recharts:
 *   fill={CHART_COLORS.primary}
 *   stroke={CHART_COLORS.secondary}
 */
export const CHART_COLORS = {
  // Primary brand colors
  primary: 'var(--color-teal-electric)',
  primaryLight: 'var(--color-teal-glow)',

  // Semantic colors
  success: 'var(--color-teal-electric)',
  warning: 'var(--color-amber-warn)',
  danger: 'var(--color-coral-alert)',
  info: 'var(--color-blue-info)',

  // Extended palette for multi-series charts
  palette: [
    'var(--color-teal-electric)',    // Teal (primary)
    'var(--color-blue-info)',        // Blue
    'var(--color-purple-accent)',    // Purple
    'var(--color-amber-warn)',       // Amber
    'var(--color-coral-alert)',      // Coral
    'var(--color-cyan-accent)',      // Cyan
  ],

  // Neutral colors for axes, grids, labels
  axis: 'var(--color-slate-muted)',
  grid: 'var(--color-slate-border)',
  label: 'var(--color-slate-muted)',

  // Tooltip styling
  tooltip: {
    bg: 'var(--color-slate-card)',
    border: 'var(--color-slate-border)',
    text: 'var(--color-text-primary)',
  },
} as const;

/**
 * Get chart color by index (cycles through palette)
 */
export function getChartColor(index: number): string {
  return CHART_COLORS.palette[index % CHART_COLORS.palette.length];
}

// =============================================================================
// STATUS MAPPING
// =============================================================================

/**
 * Maps status strings to variants.
 * Used by StatusBadge and other status-aware components.
 */
export const STATUS_VARIANT_MAP: Record<string, Variant> = {
  // Success states
  active: 'success',
  completed: 'success',
  paid: 'success',
  approved: 'success',
  online: 'success',
  connected: 'success',
  healthy: 'success',
  resolved: 'success',

  // Warning states
  pending: 'warning',
  processing: 'warning',
  partial: 'warning',
  review: 'warning',
  expiring: 'warning',
  degraded: 'warning',

  // Danger states
  failed: 'danger',
  error: 'danger',
  cancelled: 'danger',
  overdue: 'danger',
  offline: 'danger',
  critical: 'danger',
  rejected: 'danger',

  // Info states
  draft: 'info',
  new: 'info',
  scheduled: 'info',

  // Default fallback
  inactive: 'default',
  unknown: 'default',
};

/**
 * Get variant for a status string
 */
export function getStatusVariant(status: string): Variant {
  const normalized = status.toLowerCase().replace(/[_-]/g, '');
  return STATUS_VARIANT_MAP[normalized] ?? 'default';
}

// =============================================================================
// CSS VARIABLE REFERENCES (for Tailwind config)
// =============================================================================

/**
 * Color references for Tailwind config.
 * All colors use CSS variables for theme switching.
 */
export const TAILWIND_COLORS = {
  // Slate palette (backgrounds, borders)
  'slate-deep': 'var(--color-slate-deep)',
  'slate-card': 'var(--color-slate-card)',
  'slate-elevated': 'var(--color-slate-elevated)',
  'slate-border': 'var(--color-slate-border)',
  'slate-muted': 'var(--color-slate-muted)',

  // Brand colors
  'teal-electric': 'var(--color-teal-electric)',
  'teal-glow': 'var(--color-teal-glow)',

  // Semantic colors
  'coral-alert': 'var(--color-coral-alert)',
  'amber-warn': 'var(--color-amber-warn)',
  'blue-info': 'var(--color-blue-info)',
  'purple-accent': 'var(--color-purple-accent)',
  'cyan-accent': 'var(--color-cyan-accent)',
} as const;
