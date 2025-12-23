/**
 * Centralized module registry for Dotmac Insights
 * Defines all available modules, their metadata, and categories
 *
 * This is the single source of truth for:
 * - Module identifiers and labels
 * - Layout shell assignments (which sidebar to show)
 * - Module brand colors (via AccentColor)
 * - Path-to-module mapping
 */

import { LucideIcon } from 'lucide-react';
import {
  LayoutDashboard,
  Users,
  Briefcase,
  BookOpen,
  LifeBuoy,
  Wallet2,
  ShoppingCart,
  Bell,
  ShieldCheck,
  MessageSquare,
  Truck,
  Car,
  FolderKanban,
  Package,
  Landmark,
  Contact2,
  Database,
  CheckSquare,
} from 'lucide-react';
import { getButtonColors, type AccentColor, type ButtonColorConfig } from './colors';
import type { Scope } from '@/lib/auth-context';

// Re-export ButtonColorConfig for convenience
export type { ButtonColorConfig };

// Re-export Scope for consumers that import from modules.ts
export type { Scope };

export type ModuleCategory = 'core' | 'operations' | 'finance' | 'admin';

/** Layout shell type - determines which sidebar navigation to render */
export type LayoutShell = 'books' | 'hr' | 'default';

export interface ModuleDefinition {
  key: string;
  name: string;
  description: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
  accentColor: AccentColor;
  requiredScopes?: Scope[];
  stub?: boolean;
  category: ModuleCategory;
  /** Which layout shell to use for this module's routes */
  shell: LayoutShell;
}

export type ModuleKey = ModuleDefinition['key'];

export const MODULES: ModuleDefinition[] = [
  // Core Operations
  {
    key: 'crm',
    name: 'CRM',
    description: 'Unified contact and pipeline management.',
    href: '/crm',
    icon: Contact2,
    badge: 'CRM',
    accentColor: 'cyan',
    category: 'core',
    shell: 'default',
    requiredScopes: ['crm:read'],
  },
  {
    key: 'contacts',
    name: 'Contacts',
    description: 'Unified contact management for customers, leads, and suppliers.',
    href: '/contacts',
    icon: Contact2,
    badge: 'CRM',
    accentColor: 'indigo',
    category: 'core',
    shell: 'default',
    requiredScopes: ['contacts:read'],
  },
  {
    key: 'hr',
    name: 'People',
    description: 'HR operations, payroll, leave, attendance, and workforce analytics.',
    href: '/hr',
    icon: Briefcase,
    badge: 'HR',
    accentColor: 'amber',
    requiredScopes: ['hr:read'],
    category: 'operations',
    shell: 'hr',
  },
  {
    key: 'fleet',
    name: 'Fleet',
    description: 'Vehicle tracking, insurance, and driver assignments.',
    href: '/fleet',
    icon: Car,
    badge: 'Ops',
    accentColor: 'orange',
    requiredScopes: ['fleet:read'],
    category: 'operations',
    shell: 'default',
  },
  {
    key: 'support',
    name: 'Support',
    description: 'Omnichannel helpdesk, tickets, SLAs, CSAT, and automation.',
    href: '/support',
    icon: LifeBuoy,
    badge: 'Helpdesk',
    accentColor: 'teal',
    category: 'core',
    shell: 'default',
    requiredScopes: ['support:read'],
  },
  {
    key: 'inbox',
    name: 'Inbox',
    description: 'Unified conversations across email, chat, WhatsApp, and phone.',
    href: '/inbox',
    icon: MessageSquare,
    badge: 'Omnichannel',
    accentColor: 'blue',
    category: 'core',
    shell: 'default',
    requiredScopes: ['inbox:read'],
  },
  {
    key: 'sales',
    name: 'Sales',
    description: 'Invoices, quotations, orders, and customer management.',
    href: '/sales',
    icon: Users,
    badge: 'CRM',
    accentColor: 'emerald',
    requiredScopes: ['analytics:read'],
    category: 'core',
    shell: 'default',
  },
  // Operations
  {
    key: 'inventory',
    name: 'Inventory',
    description: 'Warehouse management, stock levels, batches, and serial tracking.',
    href: '/inventory',
    icon: Package,
    badge: 'WMS',
    accentColor: 'lime',
    category: 'operations',
    shell: 'books',
    requiredScopes: ['inventory:read'],
  },
  {
    key: 'field-service',
    name: 'Field Service',
    description: 'Dispatch, scheduling, service orders, and technician management.',
    href: '/field-service',
    icon: Truck,
    badge: 'FSM',
    accentColor: 'orange',
    category: 'operations',
    shell: 'default',
    requiredScopes: ['field-service:read'],
  },
  {
    key: 'projects',
    name: 'Projects',
    description: 'Project management, tasks, milestones, and resource allocation.',
    href: '/projects',
    icon: FolderKanban,
    badge: 'PM',
    accentColor: 'purple',
    category: 'operations',
    shell: 'default',
    requiredScopes: ['projects:read'],
  },
  {
    key: 'purchasing',
    name: 'Purchasing',
    description: 'Vendor management, bills, purchase orders, and AP aging.',
    href: '/purchasing',
    icon: ShoppingCart,
    badge: 'Procurement',
    accentColor: 'violet',
    requiredScopes: ['purchasing:read'],
    category: 'operations',
    shell: 'default',
  },
  // Finance
  {
    key: 'books',
    name: 'Books',
    description: 'Accounting hub with ledger, AR/AP, tax compliance, and controls.',
    href: '/books',
    icon: BookOpen,
    badge: 'Accounting',
    accentColor: 'teal',
    requiredScopes: ['books:read'],
    category: 'finance',
    shell: 'books',
  },
  {
    key: 'reports',
    name: 'Reports',
    description: 'Financial reports, dashboards, and analytics.',
    href: '/reports',
    icon: LayoutDashboard,
    badge: 'Analytics',
    accentColor: 'teal',
    requiredScopes: ['reports:read'],
    category: 'finance',
    shell: 'books',
  },
  {
    key: 'assets',
    name: 'Assets',
    description: 'Fixed asset tracking, depreciation schedules, and maintenance.',
    href: '/assets',
    icon: Landmark,
    badge: 'FAM',
    accentColor: 'stone',
    category: 'finance',
    shell: 'default',
    requiredScopes: ['assets:read'],
  },
  {
    key: 'expenses',
    name: 'Expenses',
    description: 'Expense claims, cash advances, corporate cards, and reconciliation.',
    href: '/expenses',
    icon: Wallet2,
    badge: 'Spend',
    accentColor: 'sky',
    requiredScopes: ['expenses:read'],
    category: 'finance',
    shell: 'default',
  },
  {
    key: 'analytics',
    name: 'Analytics',
    description: 'Cross-domain dashboards, reports, and business insights.',
    href: '/analytics',
    icon: LayoutDashboard,
    accentColor: 'cyan',
    requiredScopes: ['analytics:read'],
    category: 'finance',
    shell: 'default',
  },
  {
    key: 'explorer',
    name: 'Data Explorer',
    description: 'Browse data models, query records, and export reports.',
    href: '/explorer',
    icon: Database,
    accentColor: 'slate',
    requiredScopes: ['explorer:read'],
    category: 'admin',
    shell: 'default',
  },
  // Workflow
  {
    key: 'tasks',
    name: 'My Tasks',
    description: 'Unified workflow tasks from all modules.',
    href: '/tasks',
    icon: CheckSquare,
    badge: 'Workflow',
    accentColor: 'indigo',
    category: 'core',
    shell: 'default',
  },
  // Admin
  {
    key: 'notifications',
    name: 'Notifications',
    description: 'Email, SMS, in-app digests and delivery logs.',
    href: '/notifications',
    icon: Bell,
    accentColor: 'rose',
    requiredScopes: ['admin:read'],
    category: 'admin',
    shell: 'default',
  },
  {
    key: 'security',
    name: 'Controls',
    description: 'Access management, audit trails, and data protections.',
    href: '/admin/security',
    icon: ShieldCheck,
    accentColor: 'slate',
    requiredScopes: ['admin:read'],
    category: 'admin',
    shell: 'default',
  },
];

export interface CategoryMeta {
  label: string;
  description: string;
}

export const CATEGORY_META: Record<ModuleCategory, CategoryMeta> = {
  core: { label: 'Core', description: 'Customer-facing operations' },
  operations: { label: 'Operations', description: 'Internal workflows' },
  finance: { label: 'Finance', description: 'Financial management' },
  admin: { label: 'Admin', description: 'System administration' },
};

/**
 * Get a module by its key
 */
export function getModule(key: string): ModuleDefinition | undefined {
  return MODULES.find((m) => m.key === key);
}

/**
 * Get all modules in a specific category
 */
export function getModulesByCategory(category: ModuleCategory): ModuleDefinition[] {
  return MODULES.filter((m) => m.category === category);
}

/**
 * Get all module categories with their modules
 */
export function getModulesGroupedByCategory(): Record<ModuleCategory, ModuleDefinition[]> {
  return {
    core: getModulesByCategory('core'),
    operations: getModulesByCategory('operations'),
    finance: getModulesByCategory('finance'),
    admin: getModulesByCategory('admin'),
  };
}

/**
 * Get modules that require specific scopes
 */
export function getModulesRequiringScope(scope: Scope): ModuleDefinition[] {
  return MODULES.filter((m) => m.requiredScopes?.includes(scope));
}

/**
 * Check if a module is accessible based on user scopes
 */
export function isModuleAccessible(moduleKey: string, userScopes: Scope[]): boolean {
  const moduleDef = getModule(moduleKey);
  if (!moduleDef) return false;
  if (!moduleDef.requiredScopes || moduleDef.requiredScopes.length === 0) return true;
  if (userScopes.includes('*')) return true;
  return moduleDef.requiredScopes.some((scope) => userScopes.includes(scope));
}

// -----------------------------------------------------------------------------
// Path-to-Module Mapping
// -----------------------------------------------------------------------------

/**
 * Maps URL path segments to module keys.
 * Some paths map to different modules (e.g., 'performance' -> 'hr')
 */
const PATH_TO_MODULE_KEY: Record<string, string> = {
  books: 'books',
  sales: 'sales',
  expenses: 'expenses',
  hr: 'hr',
  fleet: 'fleet',
  purchasing: 'purchasing',
  inventory: 'inventory',
  support: 'support',
  contacts: 'crm', // Redirect old contacts to CRM
  crm: 'crm',
  admin: 'security',
  insights: 'analytics',
  analytics: 'analytics',
  performance: 'hr',
  projects: 'projects',
  reports: 'reports',
  'field-service': 'field-service',
  assets: 'assets',
  explorer: 'explorer',
  inbox: 'inbox',
  notifications: 'notifications',
  customers: 'sales',
  tasks: 'tasks',
};

/**
 * Special path rules that override the simple segment mapping.
 * Returns the shell to use, or null if no special rule applies.
 */
function getSpecialPathShell(pathname: string): LayoutShell | null {
  // /sales/customers uses the books shell (AR management)
  if (pathname.startsWith('/sales/customers')) {
    return 'books';
  }
  return null;
}

/**
 * Get module from URL pathname
 */
export function getModuleFromPath(pathname: string): ModuleDefinition | undefined {
  const segments = pathname.split('/').filter(Boolean);
  const firstSegment = segments[0]?.toLowerCase();
  const moduleKey = PATH_TO_MODULE_KEY[firstSegment];
  return moduleKey ? getModule(moduleKey) : undefined;
}

/**
 * Determine which layout shell to use for a given pathname
 */
export function getLayoutShell(pathname: string): LayoutShell {
  // Check for special path rules first
  const specialShell = getSpecialPathShell(pathname);
  if (specialShell) {
    return specialShell;
  }

  // Get module from path and return its shell
  const moduleDef = getModuleFromPath(pathname);
  if (moduleDef) {
    return moduleDef.shell;
  }

  return 'default';
}

/**
 * Check if a pathname should use the books shell
 */
export function isBooksShell(pathname: string): boolean {
  return getLayoutShell(pathname) === 'books';
}

/**
 * Check if a pathname should use the HR shell
 */
export function isHrShell(pathname: string): boolean {
  return getLayoutShell(pathname) === 'hr';
}

/**
 * Get all modules that use a specific shell
 */
export function getModulesByShell(shell: LayoutShell): ModuleDefinition[] {
  return MODULES.filter((m) => m.shell === shell);
}

// -----------------------------------------------------------------------------
// Button Colors (convenience helpers)
// -----------------------------------------------------------------------------

/**
 * Get button colors for a module by key.
 *
 * @example
 * const colors = getModuleButtonColors('sales');
 * <button className={`${colors.primary} ${colors.primaryHover}`}>Action</button>
 */
export function getModuleButtonColors(moduleKey: string): ButtonColorConfig {
  const moduleDef = getModule(moduleKey);
  return getButtonColors(moduleDef?.accentColor ?? 'teal');
}

/**
 * Get button colors from a URL pathname.
 *
 * @example
 * const colors = getButtonColorsFromPath('/sales/invoices');
 * <button className={`${colors.primary} ${colors.primaryHover}`}>Action</button>
 */
export function getButtonColorsFromPath(pathname: string): ButtonColorConfig {
  const moduleDef = getModuleFromPath(pathname);
  return getButtonColors(moduleDef?.accentColor ?? 'teal');
}
