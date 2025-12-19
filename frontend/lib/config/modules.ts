/**
 * Centralized module registry for Dotmac Insights
 * Defines all available modules, their metadata, and categories
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
  FolderKanban,
  Package,
  Landmark,
  Contact2,
} from 'lucide-react';
import type { AccentColor } from './colors';

export type ModuleCategory = 'core' | 'operations' | 'finance' | 'admin';

export type Scope =
  | 'hr:read'
  | 'hr:write'
  | 'analytics:read'
  | 'analytics:write'
  | 'admin:read'
  | 'admin:write'
  | '*';

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
}

export const MODULES: ModuleDefinition[] = [
  // Core Operations
  {
    key: 'contacts',
    name: 'Contacts',
    description: 'Unified contact management for customers, leads, and suppliers.',
    href: '/contacts',
    icon: Contact2,
    badge: 'CRM',
    accentColor: 'indigo',
    category: 'core',
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
  },
  {
    key: 'purchasing',
    name: 'Purchasing',
    description: 'Vendor management, bills, purchase orders, and AP aging.',
    href: '/purchasing',
    icon: ShoppingCart,
    badge: 'Procurement',
    accentColor: 'violet',
    requiredScopes: ['analytics:read'],
    category: 'operations',
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
    requiredScopes: ['analytics:read'],
    category: 'finance',
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
  },
  {
    key: 'expenses',
    name: 'Expenses',
    description: 'Expense claims, cash advances, corporate cards, and reconciliation.',
    href: '/expenses',
    icon: Wallet2,
    badge: 'Spend',
    accentColor: 'sky',
    requiredScopes: ['analytics:read'],
    category: 'finance',
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
