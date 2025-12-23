'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useTheme } from '@dotmac/design-tokens';
import { useAuth } from '@/lib/auth-context';
import { applyColorScheme } from '@/lib/theme';
import { getSidebarColors } from '@/lib/config/colors';
import { useCommandPalette } from '@/components/CommandPaletteProvider';
import { ModuleLayoutContext } from './context';
import { getActiveSection, getActiveHref } from './utils';
import { ModuleHeader } from './ModuleHeader';
import { MobileNav } from './MobileNav';
import { ModuleSidebar } from './ModuleSidebar';
import type { ModuleLayoutProps } from './types';

// =============================================================================
// COMPONENT
// =============================================================================

/**
 * Module layout orchestrator component
 *
 * Provides a consistent layout pattern for module pages with:
 * - Desktop top bar with branding and actions
 * - Mobile-responsive navigation with drawer
 * - Sidebar with collapsible navigation sections
 * - Workflow phase indicators
 * - Quick links grid
 *
 * @example
 * ```tsx
 * <ModuleLayout
 *   moduleName="Dotmac Books"
 *   moduleSubtitle="Finance & Accounting"
 *   sidebarTitle="Accounting"
 *   sidebarDescription="Manage your finances"
 *   baseRoute="/books"
 *   accentColor="teal"
 *   icon={Calculator}
 *   sections={navigationSections}
 * >
 *   <YourPageContent />
 * </ModuleLayout>
 * ```
 */
export function ModuleLayout({
  moduleName,
  moduleSubtitle,
  sidebarTitle,
  sidebarDescription,
  baseRoute,
  accentColor,
  icon,
  sections,
  quickLinks,
  workflowPhases,
  getWorkflowPhase,
  workflowSteps,
  headerContent,
  children,
}: ModuleLayoutProps) {
  const pathname = usePathname();
  const { isDarkMode, setColorScheme } = useTheme();
  const { isAuthenticated, logout } = useAuth();
  const { open: openCommandPalette } = useCommandPalette();
  const colors = getSidebarColors(accentColor);

  // Theme toggle handler
  const toggleTheme = useCallback(() => {
    const next = isDarkMode ? 'light' : 'dark';
    setColorScheme(next);
    applyColorScheme(next);
  }, [isDarkMode, setColorScheme]);

  // Initialize open sections with active section expanded
  const [openSections, setOpenSections] = useState<Record<string, boolean>>(() => {
    const activeSection = getActiveSection(pathname, sections, baseRoute);
    const initial: Record<string, boolean> = {};
    sections.forEach((s) => {
      initial[s.key] = s.key === 'overview' || s.key === activeSection;
    });
    return initial;
  });

  // Keep the active section open on route change
  useEffect(() => {
    const activeSection = getActiveSection(pathname, sections, baseRoute);
    if (!activeSection) return;
    setOpenSections((prev) => ({ ...prev, [activeSection]: true }));
  }, [pathname, sections, baseRoute]);

  // Memoized computed values
  const activeSection = useMemo(
    () => getActiveSection(pathname, sections, baseRoute),
    [pathname, sections, baseRoute]
  );

  const currentPhase = useMemo(() => {
    if (getWorkflowPhase) {
      return getWorkflowPhase(activeSection);
    }
    if (!workflowPhases || workflowPhases.length === 0) {
      return '';
    }
    if (!activeSection) {
      return workflowPhases[0].key;
    }
    const sectionIndex = sections.findIndex((section) => section.key === activeSection);
    if (sectionIndex >= 0 && sectionIndex < workflowPhases.length) {
      return workflowPhases[sectionIndex].key;
    }
    return workflowPhases[0].key;
  }, [activeSection, getWorkflowPhase, workflowPhases, sections]);

  const activeHref = useMemo(
    () => getActiveHref(pathname, sections, baseRoute),
    [pathname, sections, baseRoute]
  );

  const toggleSection = useCallback((key: string) => {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // Context value
  const contextValue = useMemo(
    () => ({
      colors,
      baseRoute,
      pathname,
      activeSection,
      activeHref,
      currentPhase,
      sections,
      openSections,
      toggleSection,
      workflowPhases,
      getWorkflowPhase,
      toggleTheme,
      isDarkMode,
      isAuthenticated,
      logout,
      openCommandPalette,
    }),
    [
      colors,
      baseRoute,
      pathname,
      activeSection,
      activeHref,
      currentPhase,
      sections,
      openSections,
      toggleSection,
      workflowPhases,
      getWorkflowPhase,
      toggleTheme,
      isDarkMode,
      isAuthenticated,
      logout,
      openCommandPalette,
    ]
  );

  return (
    <ModuleLayoutContext.Provider value={contextValue}>
      <div className="space-y-4">
        {/* Mobile Navigation */}
        <MobileNav
          moduleName={moduleName}
          moduleSubtitle={moduleSubtitle}
          icon={icon}
          quickLinks={quickLinks}
          headerContent={headerContent}
        />

        {/* Desktop Header */}
        <ModuleHeader
          moduleName={moduleName}
          moduleSubtitle={moduleSubtitle}
          icon={icon}
          headerContent={headerContent}
        />

        {/* Main Layout Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6 pt-[64px] lg:pt-0">
          {/* Sidebar */}
          <ModuleSidebar
            sidebarTitle={sidebarTitle}
            sidebarDescription={sidebarDescription}
            quickLinks={quickLinks}
            workflowSteps={workflowSteps}
          />

          {/* Main Content */}
          <div className="space-y-6">{children}</div>
        </div>
      </div>
    </ModuleLayoutContext.Provider>
  );
}

export default ModuleLayout;
