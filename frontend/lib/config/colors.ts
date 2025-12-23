/**
 * Unified color system for Dotmac Insights
 * Consolidates color definitions from ModuleLayout, ModuleCard, and page.tsx
 */

export type AccentColor =
  | 'amber'
  | 'teal'
  | 'sky'
  | 'violet'
  | 'emerald'
  | 'rose'
  | 'cyan'
  | 'indigo'
  | 'orange'
  | 'blue'
  | 'purple'
  | 'lime'
  | 'stone'
  | 'slate';

export interface AccentColorConfig {
  // For sidebar/ModuleLayout
  gradient: string;
  iconBg: string;
  iconText: string;
  activeBorder: string;
  activeBg: string;
  activeText: string;
  activeItemBg: string;
  activeItemText: string;
  activeDescText: string;
  // For cards/ModuleCard/badges
  cardBg: string;
  cardBorder: string;
  cardText: string;
  cardGlow: string;
  cardIcon: string;
}

export const ACCENT_COLORS: Record<AccentColor, AccentColorConfig> = {
  amber: {
    gradient: 'from-amber-400 to-amber-300',
    iconBg: 'bg-gradient-to-br from-amber-400 to-amber-300',
    iconText: 'text-amber-300',
    activeBorder: 'border-amber-500/40',
    activeBg: 'bg-amber-500/5',
    activeText: 'text-amber-300',
    activeItemBg: 'bg-amber-500/20',
    activeItemText: 'text-amber-300',
    activeDescText: 'text-amber-400/70',
    cardBg: 'bg-amber-500/10',
    cardBorder: 'border-amber-500/30',
    cardText: 'text-amber-400',
    cardGlow: 'group-hover:shadow-amber-500/20',
    cardIcon: 'from-amber-400 to-amber-300',
  },
  teal: {
    gradient: 'from-teal-400 to-teal-300',
    iconBg: 'bg-gradient-to-br from-teal-400 to-teal-300',
    iconText: 'text-teal-300',
    activeBorder: 'border-teal-500/40',
    activeBg: 'bg-teal-500/5',
    activeText: 'text-teal-300',
    activeItemBg: 'bg-teal-500/20',
    activeItemText: 'text-teal-300',
    activeDescText: 'text-teal-400/70',
    cardBg: 'bg-teal-500/10',
    cardBorder: 'border-teal-500/30',
    cardText: 'text-teal-400',
    cardGlow: 'group-hover:shadow-teal-500/20',
    cardIcon: 'from-teal-400 to-teal-300',
  },
  sky: {
    gradient: 'from-sky-500 to-emerald-400',
    iconBg: 'bg-gradient-to-br from-sky-500 to-emerald-400',
    iconText: 'text-sky-300',
    activeBorder: 'border-sky-500/40',
    activeBg: 'bg-sky-500/5',
    activeText: 'text-sky-300',
    activeItemBg: 'bg-sky-500/20',
    activeItemText: 'text-sky-300',
    activeDescText: 'text-sky-400/70',
    cardBg: 'bg-sky-500/10',
    cardBorder: 'border-sky-500/30',
    cardText: 'text-sky-400',
    cardGlow: 'group-hover:shadow-sky-500/20',
    cardIcon: 'from-sky-400 to-sky-300',
  },
  violet: {
    gradient: 'from-violet-400 to-violet-300',
    iconBg: 'bg-gradient-to-br from-violet-400 to-violet-300',
    iconText: 'text-violet-300',
    activeBorder: 'border-violet-500/40',
    activeBg: 'bg-violet-500/5',
    activeText: 'text-violet-300',
    activeItemBg: 'bg-violet-500/20',
    activeItemText: 'text-violet-300',
    activeDescText: 'text-violet-400/70',
    cardBg: 'bg-violet-500/10',
    cardBorder: 'border-violet-500/30',
    cardText: 'text-violet-400',
    cardGlow: 'group-hover:shadow-violet-500/20',
    cardIcon: 'from-violet-400 to-violet-300',
  },
  emerald: {
    gradient: 'from-emerald-400 to-emerald-300',
    iconBg: 'bg-gradient-to-br from-emerald-400 to-emerald-300',
    iconText: 'text-emerald-300',
    activeBorder: 'border-emerald-500/40',
    activeBg: 'bg-emerald-500/5',
    activeText: 'text-emerald-300',
    activeItemBg: 'bg-emerald-500/20',
    activeItemText: 'text-emerald-300',
    activeDescText: 'text-emerald-400/70',
    cardBg: 'bg-emerald-500/10',
    cardBorder: 'border-emerald-500/30',
    cardText: 'text-emerald-400',
    cardGlow: 'group-hover:shadow-emerald-500/20',
    cardIcon: 'from-emerald-400 to-emerald-300',
  },
  rose: {
    gradient: 'from-rose-400 to-rose-300',
    iconBg: 'bg-gradient-to-br from-rose-400 to-rose-300',
    iconText: 'text-rose-300',
    activeBorder: 'border-rose-500/40',
    activeBg: 'bg-rose-500/5',
    activeText: 'text-rose-300',
    activeItemBg: 'bg-rose-500/20',
    activeItemText: 'text-rose-300',
    activeDescText: 'text-rose-400/70',
    cardBg: 'bg-rose-500/10',
    cardBorder: 'border-rose-500/30',
    cardText: 'text-rose-400',
    cardGlow: 'group-hover:shadow-rose-500/20',
    cardIcon: 'from-rose-400 to-rose-300',
  },
  cyan: {
    gradient: 'from-cyan-400 to-cyan-300',
    iconBg: 'bg-gradient-to-br from-cyan-400 to-cyan-300',
    iconText: 'text-cyan-300',
    activeBorder: 'border-cyan-500/40',
    activeBg: 'bg-cyan-500/5',
    activeText: 'text-cyan-300',
    activeItemBg: 'bg-cyan-500/20',
    activeItemText: 'text-cyan-300',
    activeDescText: 'text-cyan-400/70',
    cardBg: 'bg-cyan-500/10',
    cardBorder: 'border-cyan-500/30',
    cardText: 'text-cyan-400',
    cardGlow: 'group-hover:shadow-cyan-500/20',
    cardIcon: 'from-cyan-400 to-cyan-300',
  },
  indigo: {
    gradient: 'from-indigo-500 to-purple-400',
    iconBg: 'bg-gradient-to-br from-indigo-500 to-purple-400',
    iconText: 'text-indigo-300',
    activeBorder: 'border-indigo-500/40',
    activeBg: 'bg-indigo-500/5',
    activeText: 'text-indigo-300',
    activeItemBg: 'bg-indigo-500/20',
    activeItemText: 'text-indigo-300',
    activeDescText: 'text-indigo-400/70',
    cardBg: 'bg-indigo-500/10',
    cardBorder: 'border-indigo-500/30',
    cardText: 'text-indigo-400',
    cardGlow: 'group-hover:shadow-indigo-500/20',
    cardIcon: 'from-indigo-400 to-indigo-300',
  },
  orange: {
    gradient: 'from-orange-500 to-amber-400',
    iconBg: 'bg-gradient-to-br from-orange-500 to-amber-400',
    iconText: 'text-orange-300',
    activeBorder: 'border-orange-500/40',
    activeBg: 'bg-orange-500/5',
    activeText: 'text-orange-300',
    activeItemBg: 'bg-orange-500/20',
    activeItemText: 'text-orange-300',
    activeDescText: 'text-orange-400/70',
    cardBg: 'bg-orange-500/10',
    cardBorder: 'border-orange-500/30',
    cardText: 'text-orange-400',
    cardGlow: 'group-hover:shadow-orange-500/20',
    cardIcon: 'from-orange-400 to-orange-300',
  },
  blue: {
    gradient: 'from-blue-500 to-cyan-400',
    iconBg: 'bg-gradient-to-br from-blue-500 to-cyan-400',
    iconText: 'text-blue-300',
    activeBorder: 'border-blue-500/40',
    activeBg: 'bg-blue-500/5',
    activeText: 'text-blue-300',
    activeItemBg: 'bg-blue-500/20',
    activeItemText: 'text-blue-300',
    activeDescText: 'text-blue-400/70',
    cardBg: 'bg-blue-500/10',
    cardBorder: 'border-blue-500/30',
    cardText: 'text-blue-400',
    cardGlow: 'group-hover:shadow-blue-500/20',
    cardIcon: 'from-blue-500 to-cyan-400',
  },
  purple: {
    gradient: 'from-purple-400 to-purple-300',
    iconBg: 'bg-gradient-to-br from-purple-400 to-purple-300',
    iconText: 'text-purple-300',
    activeBorder: 'border-purple-500/40',
    activeBg: 'bg-purple-500/5',
    activeText: 'text-purple-300',
    activeItemBg: 'bg-purple-500/20',
    activeItemText: 'text-purple-300',
    activeDescText: 'text-purple-400/70',
    cardBg: 'bg-purple-500/10',
    cardBorder: 'border-purple-500/30',
    cardText: 'text-purple-400',
    cardGlow: 'group-hover:shadow-purple-500/20',
    cardIcon: 'from-purple-400 to-purple-300',
  },
  lime: {
    gradient: 'from-lime-400 to-lime-300',
    iconBg: 'bg-gradient-to-br from-lime-400 to-lime-300',
    iconText: 'text-lime-300',
    activeBorder: 'border-lime-500/40',
    activeBg: 'bg-lime-500/5',
    activeText: 'text-lime-300',
    activeItemBg: 'bg-lime-500/20',
    activeItemText: 'text-lime-300',
    activeDescText: 'text-lime-400/70',
    cardBg: 'bg-lime-500/10',
    cardBorder: 'border-lime-500/30',
    cardText: 'text-lime-400',
    cardGlow: 'group-hover:shadow-lime-500/20',
    cardIcon: 'from-lime-400 to-lime-300',
  },
  stone: {
    gradient: 'from-stone-400 to-stone-300',
    iconBg: 'bg-gradient-to-br from-stone-400 to-stone-300',
    iconText: 'text-stone-300',
    activeBorder: 'border-stone-500/40',
    activeBg: 'bg-stone-500/5',
    activeText: 'text-stone-300',
    activeItemBg: 'bg-stone-500/20',
    activeItemText: 'text-stone-300',
    activeDescText: 'text-stone-400/70',
    cardBg: 'bg-stone-500/10',
    cardBorder: 'border-stone-500/30',
    cardText: 'text-stone-400',
    cardGlow: 'group-hover:shadow-stone-500/20',
    cardIcon: 'from-stone-400 to-stone-300',
  },
  slate: {
    gradient: 'from-slate-400 to-slate-300',
    iconBg: 'bg-gradient-to-br from-slate-400 to-slate-300',
    iconText: 'text-foreground-secondary',
    activeBorder: 'border-slate-500/40',
    activeBg: 'bg-slate-500/5',
    activeText: 'text-foreground-secondary',
    activeItemBg: 'bg-slate-500/20',
    activeItemText: 'text-foreground-secondary',
    activeDescText: 'text-slate-400/70',
    cardBg: 'bg-slate-500/10',
    cardBorder: 'border-slate-500/30',
    cardText: 'text-slate-400',
    cardGlow: 'group-hover:shadow-slate-500/20',
    cardIcon: 'from-slate-400 to-slate-300',
  },
};

/**
 * Get accent color configuration with fallback
 */
export function getAccentColors(color: AccentColor): AccentColorConfig {
  return ACCENT_COLORS[color] ?? ACCENT_COLORS.teal;
}

/**
 * Helper to get sidebar-specific colors (for ModuleLayout)
 */
export function getSidebarColors(color: AccentColor) {
  const config = getAccentColors(color);
  return {
    gradient: config.gradient,
    iconBg: config.iconBg,
    iconText: config.iconText,
    activeBorder: config.activeBorder,
    activeBg: config.activeBg,
    activeText: config.activeText,
    activeItemBg: config.activeItemBg,
    activeItemText: config.activeItemText,
    activeDescText: config.activeDescText,
  };
}

/**
 * Helper to get card-specific colors (for ModuleCard, badges)
 */
export function getCardColors(color: AccentColor) {
  const config = getAccentColors(color);
  return {
    bg: config.cardBg,
    border: config.cardBorder,
    text: config.cardText,
    glow: config.cardGlow,
    icon: config.cardIcon,
  };
}

// =============================================================================
// BUTTON COLORS
// =============================================================================

export interface ButtonColorConfig {
  /** Primary filled button background */
  primary: string;
  /** Primary button hover state */
  primaryHover: string;
  /** Primary text/icon color */
  primaryText: string;
  /** Light background for badges/chips */
  primaryBg: string;
  /** Border color for outlined elements */
  primaryBorder: string;
}

/**
 * Button color mappings derived from AccentColor.
 * This consolidates the MODULE_COLORS pattern from module-colors.ts.
 */
const BUTTON_COLORS: Record<AccentColor, ButtonColorConfig> = {
  amber: {
    primary: 'bg-amber-500',
    primaryHover: 'hover:bg-amber-400',
    primaryText: 'text-amber-500',
    primaryBg: 'bg-amber-500/10',
    primaryBorder: 'border-amber-500/30',
  },
  teal: {
    primary: 'bg-teal-electric',
    primaryHover: 'hover:bg-teal-electric/90',
    primaryText: 'text-teal-electric',
    primaryBg: 'bg-teal-electric/10',
    primaryBorder: 'border-teal-electric/30',
  },
  sky: {
    primary: 'bg-sky-500',
    primaryHover: 'hover:bg-sky-400',
    primaryText: 'text-sky-500',
    primaryBg: 'bg-sky-500/10',
    primaryBorder: 'border-sky-500/30',
  },
  violet: {
    primary: 'bg-violet-500',
    primaryHover: 'hover:bg-violet-400',
    primaryText: 'text-violet-500',
    primaryBg: 'bg-violet-500/10',
    primaryBorder: 'border-violet-500/30',
  },
  emerald: {
    primary: 'bg-emerald-500',
    primaryHover: 'hover:bg-emerald-400',
    primaryText: 'text-emerald-500',
    primaryBg: 'bg-emerald-500/10',
    primaryBorder: 'border-emerald-500/30',
  },
  rose: {
    primary: 'bg-rose-500',
    primaryHover: 'hover:bg-rose-400',
    primaryText: 'text-rose-500',
    primaryBg: 'bg-rose-500/10',
    primaryBorder: 'border-rose-500/30',
  },
  cyan: {
    primary: 'bg-cyan-500',
    primaryHover: 'hover:bg-cyan-400',
    primaryText: 'text-cyan-500',
    primaryBg: 'bg-cyan-500/10',
    primaryBorder: 'border-cyan-500/30',
  },
  indigo: {
    primary: 'bg-indigo-500',
    primaryHover: 'hover:bg-indigo-400',
    primaryText: 'text-indigo-500',
    primaryBg: 'bg-indigo-500/10',
    primaryBorder: 'border-indigo-500/30',
  },
  orange: {
    primary: 'bg-orange-500',
    primaryHover: 'hover:bg-orange-400',
    primaryText: 'text-orange-500',
    primaryBg: 'bg-orange-500/10',
    primaryBorder: 'border-orange-500/30',
  },
  blue: {
    primary: 'bg-blue-500',
    primaryHover: 'hover:bg-blue-400',
    primaryText: 'text-blue-500',
    primaryBg: 'bg-blue-500/10',
    primaryBorder: 'border-blue-500/30',
  },
  purple: {
    primary: 'bg-purple-500',
    primaryHover: 'hover:bg-purple-400',
    primaryText: 'text-purple-500',
    primaryBg: 'bg-purple-500/10',
    primaryBorder: 'border-purple-500/30',
  },
  lime: {
    primary: 'bg-lime-500',
    primaryHover: 'hover:bg-lime-400',
    primaryText: 'text-lime-500',
    primaryBg: 'bg-lime-500/10',
    primaryBorder: 'border-lime-500/30',
  },
  stone: {
    primary: 'bg-stone-500',
    primaryHover: 'hover:bg-stone-400',
    primaryText: 'text-stone-500',
    primaryBg: 'bg-stone-500/10',
    primaryBorder: 'border-stone-500/30',
  },
  slate: {
    primary: 'bg-slate-500',
    primaryHover: 'hover:bg-slate-400',
    primaryText: 'text-slate-400',
    primaryBg: 'bg-slate-500/10',
    primaryBorder: 'border-slate-500/30',
  },
};

/**
 * Get button-specific colors for an accent color.
 * Use this for primary action buttons, badges, and module-specific UI.
 */
export function getButtonColors(color: AccentColor): ButtonColorConfig {
  return BUTTON_COLORS[color] ?? BUTTON_COLORS.teal;
}
