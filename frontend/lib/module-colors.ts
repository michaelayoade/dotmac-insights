/**
 * MODULE COLORS - Brand color configuration for each application module
 *
 * Each module has a distinct brand color for visual identity.
 * Primary action buttons should use the module's primary color.
 *
 * Design system integration:
 * - All colors reference CSS variables from design-tokens.ts
 * - Use these in components via the `module` prop
 */

export type AppModule =
  | 'books'
  | 'sales'
  | 'expenses'
  | 'hr'
  | 'purchasing'
  | 'inventory'
  | 'support'
  | 'contacts'
  | 'admin'
  | 'insights';

export interface ModuleColorConfig {
  /** Primary action color (filled buttons) */
  primary: string;
  /** Primary hover state */
  primaryHover: string;
  /** Primary text color */
  primaryText: string;
  /** Light background for badges/chips */
  primaryBg: string;
  /** Border color for primary elements */
  primaryBorder: string;
}

/**
 * Module color definitions
 *
 * Each module has a consistent color applied to:
 * - Primary action buttons
 * - Module header accents
 * - Active navigation states
 * - Progress indicators
 */
export const MODULE_COLORS: Record<AppModule, ModuleColorConfig> = {
  books: {
    primary: 'bg-teal-electric',
    primaryHover: 'hover:bg-teal-electric/90',
    primaryText: 'text-teal-electric',
    primaryBg: 'bg-teal-electric/10',
    primaryBorder: 'border-teal-electric/30',
  },
  sales: {
    primary: 'bg-emerald-500',
    primaryHover: 'hover:bg-emerald-400',
    primaryText: 'text-emerald-500',
    primaryBg: 'bg-emerald-500/10',
    primaryBorder: 'border-emerald-500/30',
  },
  expenses: {
    primary: 'bg-sky-500',
    primaryHover: 'hover:bg-sky-400',
    primaryText: 'text-sky-500',
    primaryBg: 'bg-sky-500/10',
    primaryBorder: 'border-sky-500/30',
  },
  hr: {
    primary: 'bg-amber-500',
    primaryHover: 'hover:bg-amber-400',
    primaryText: 'text-amber-500',
    primaryBg: 'bg-amber-500/10',
    primaryBorder: 'border-amber-500/30',
  },
  purchasing: {
    primary: 'bg-violet-500',
    primaryHover: 'hover:bg-violet-400',
    primaryText: 'text-violet-500',
    primaryBg: 'bg-violet-500/10',
    primaryBorder: 'border-violet-500/30',
  },
  inventory: {
    primary: 'bg-orange-500',
    primaryHover: 'hover:bg-orange-400',
    primaryText: 'text-orange-500',
    primaryBg: 'bg-orange-500/10',
    primaryBorder: 'border-orange-500/30',
  },
  support: {
    primary: 'bg-rose-500',
    primaryHover: 'hover:bg-rose-400',
    primaryText: 'text-rose-500',
    primaryBg: 'bg-rose-500/10',
    primaryBorder: 'border-rose-500/30',
  },
  contacts: {
    primary: 'bg-cyan-500',
    primaryHover: 'hover:bg-cyan-400',
    primaryText: 'text-cyan-500',
    primaryBg: 'bg-cyan-500/10',
    primaryBorder: 'border-cyan-500/30',
  },
  admin: {
    primary: 'bg-slate-500',
    primaryHover: 'hover:bg-slate-400',
    primaryText: 'text-slate-400',
    primaryBg: 'bg-slate-500/10',
    primaryBorder: 'border-slate-500/30',
  },
  insights: {
    primary: 'bg-purple-500',
    primaryHover: 'hover:bg-purple-400',
    primaryText: 'text-purple-500',
    primaryBg: 'bg-purple-500/10',
    primaryBorder: 'border-purple-500/30',
  },
} as const;

/**
 * Get module color config by module name
 */
export function getModuleColors(module: AppModule): ModuleColorConfig {
  return MODULE_COLORS[module];
}

/**
 * Infer module from pathname
 */
export function getModuleFromPath(pathname: string): AppModule | null {
  const segments = pathname.split('/').filter(Boolean);
  const firstSegment = segments[0]?.toLowerCase();

  const moduleMap: Record<string, AppModule> = {
    books: 'books',
    sales: 'sales',
    expenses: 'expenses',
    hr: 'hr',
    purchasing: 'purchasing',
    inventory: 'inventory',
    support: 'support',
    contacts: 'contacts',
    admin: 'admin',
    insights: 'insights',
    analytics: 'insights',
    performance: 'hr',
  };

  return moduleMap[firstSegment] || null;
}

/**
 * Shared button variant styles (non-module specific)
 */
export const BUTTON_VARIANTS = {
  secondary: {
    base: 'bg-slate-elevated border border-slate-border text-foreground',
    hover: 'hover:bg-slate-border',
  },
  danger: {
    base: 'bg-coral-alert/15 border border-coral-alert/30 text-coral-alert',
    hover: 'hover:bg-coral-alert/25',
  },
  ghost: {
    base: 'text-slate-muted',
    hover: 'hover:text-foreground hover:bg-slate-elevated',
  },
  success: {
    base: 'bg-emerald-500 text-foreground',
    hover: 'hover:bg-emerald-400',
  },
} as const;
