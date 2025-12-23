/**
 * ModuleLayout - Modular layout system for application modules
 *
 * Provides a consistent layout pattern with:
 * - Desktop top bar with branding, search, and user actions
 * - Mobile-responsive navigation with slide-out drawer
 * - Sidebar with collapsible navigation sections
 * - Workflow phase indicators
 * - Quick links grid
 *
 * @example
 * ```tsx
 * import { ModuleLayout } from '@/components/ModuleLayout';
 * import type { NavSection, QuickLink } from '@/components/ModuleLayout';
 *
 * const sections: NavSection[] = [
 *   {
 *     key: 'overview',
 *     label: 'Overview',
 *     description: 'Dashboard and analytics',
 *     icon: Home,
 *     items: [
 *       { name: 'Dashboard', href: '/books' },
 *       { name: 'Reports', href: '/books/reports' },
 *     ],
 *   },
 * ];
 *
 * export default function BooksLayout({ children }) {
 *   return (
 *     <ModuleLayout
 *       moduleName="Dotmac Books"
 *       moduleSubtitle="Finance & Accounting"
 *       sidebarTitle="Accounting"
 *       sidebarDescription="Manage your finances"
 *       baseRoute="/books"
 *       accentColor="teal"
 *       icon={Calculator}
 *       sections={sections}
 *     >
 *       {children}
 *     </ModuleLayout>
 *   );
 * }
 * ```
 */

// Main component
export { ModuleLayout, ModuleLayout as default } from './ModuleLayout';

// Sub-components (for advanced customization)
export { ModuleHeader } from './ModuleHeader';
export { MobileNav } from './MobileNav';
export { ModuleSidebar } from './ModuleSidebar';
export { NavSection, NavSectionsList } from './NavSection';
export { QuickLinksGrid } from './QuickLinks';
export { WorkflowIndicator, WorkflowSteps } from './WorkflowIndicator';

// Context (for building custom sub-components)
export { ModuleLayoutContext, useModuleLayoutContext } from './context';

// Types
export type {
  ModuleLayoutProps,
  NavItem,
  NavSection as NavSectionType,
  QuickLink,
  QuickLinkColor,
  WorkflowPhase,
  WorkflowStepColor,
  WorkflowStep,
  SidebarColors,
} from './types';

// Utilities
export {
  isActivePath,
  getActiveSection,
  getActiveHref,
  getQuickLinkColorClass,
  getWorkflowStepClasses,
} from './utils';
