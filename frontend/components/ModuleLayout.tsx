'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useMemo, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useTheme } from '@dotmac/design-tokens';
import { useAuth } from '@/lib/auth-context';
import { applyColorScheme } from '@/lib/theme';
import {
  ChevronDown,
  ChevronRight,
  Sun,
  Moon,
  User,
  LogOut,
  Menu,
  X,
  LucideIcon,
  Home,
  Zap,
  Search,
} from 'lucide-react';
import { AccentColor, getSidebarColors } from '@/lib/config/colors';
import { useCommandPalette } from '@/components/CommandPaletteProvider';

// =============================================================================
// TYPES
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

export interface QuickLink {
  label: string;
  href: string;
  icon: LucideIcon;
  color: string; // e.g., "amber-400", "violet-400", "emerald-400"
}

export interface WorkflowPhase {
  key: string;
  label: string;
  description?: string;
}

export interface WorkflowStep {
  label: string;
  color: string; // e.g., "violet", "emerald", "amber"
}


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
// HELPER FUNCTIONS
// =============================================================================

function isActivePath(pathname: string, href: string, baseRoute: string) {
  if (href === baseRoute) return pathname === baseRoute;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function getActiveSection(pathname: string, sections: NavSection[], baseRoute: string): string | null {
  for (const section of sections) {
    if (section.items.some((item) => isActivePath(pathname, item.href, baseRoute))) {
      return section.key;
    }
  }
  return null;
}

function getActiveHref(pathname: string, sections: NavSection[], baseRoute: string): string {
  for (const section of sections) {
    for (const item of section.items) {
      if (isActivePath(pathname, item.href, baseRoute)) return item.href;
    }
  }
  return '';
}

// =============================================================================
// COMPONENT
// =============================================================================

export function ModuleLayout({
  moduleName,
  moduleSubtitle,
  sidebarTitle,
  sidebarDescription,
  baseRoute,
  accentColor,
  icon: ModuleIcon,
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

  const toggleTheme = () => {
    const next = isDarkMode ? 'light' : 'dark';
    setColorScheme(next);
    applyColorScheme(next);
  };

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

  const activeSection = useMemo(
    () => getActiveSection(pathname, sections, baseRoute),
    [pathname, sections, baseRoute]
  );

  const currentPhase = useMemo(
    () => (getWorkflowPhase ? getWorkflowPhase(activeSection) : workflowPhases?.[0]?.key || ''),
    [activeSection, getWorkflowPhase, workflowPhases]
  );

  const activeHref = useMemo(
    () => getActiveHref(pathname, sections, baseRoute),
    [pathname, sections, baseRoute]
  );

  const toggleSection = (key: string) => {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Render navigation sections (shared between mobile and desktop)
  const renderNavSections = (onNavigate?: () => void) => (
    <div className="space-y-2">
      {sections.map((section) => {
        const Icon = section.icon;
        const open = openSections[section.key];
        const isActiveSection = activeSection === section.key;

        return (
          <div
            key={section.key}
            className={cn(
              'border rounded-lg transition-colors',
              isActiveSection ? `${colors.activeBorder} ${colors.activeBg}` : 'border-slate-border'
            )}
          >
            <button
              onClick={() => toggleSection(section.key)}
              className="w-full flex items-center justify-between px-3 py-2.5 text-sm text-white hover:bg-slate-elevated/50 rounded-lg transition-colors"
            >
              <div className="flex items-center gap-2">
                <Icon className={cn('w-4 h-4', isActiveSection ? colors.iconText : 'text-slate-muted')} />
                <div className="text-left">
                  <span className={cn('block', isActiveSection && colors.activeText)}>{section.label}</span>
                  <span className="text-[10px] text-slate-muted">{section.description}</span>
                </div>
              </div>
              {open ? (
                <ChevronDown className="w-4 h-4 text-slate-muted" />
              ) : (
                <ChevronRight className="w-4 h-4 text-slate-muted" />
              )}
            </button>
            {open && (
              <div className="pb-2 px-2">
                {section.items.map((item) => {
                  const isActive = activeHref === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onNavigate}
                      className={cn(
                        'block px-3 py-2 text-sm rounded-lg transition-colors group',
                        isActive
                          ? `${colors.activeItemBg} ${colors.activeItemText}`
                          : 'text-slate-muted hover:text-white hover:bg-slate-elevated/50'
                      )}
                    >
                      <span className="block">{item.name}</span>
                      {item.description && (
                        <span
                          className={cn(
                            'text-[10px] block',
                            isActive ? colors.activeDescText : 'text-slate-muted group-hover:text-slate-muted'
                          )}
                        >
                          {item.description}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  // Render quick links grid
  const renderQuickLinks = (onNavigate?: () => void) =>
    quickLinks && quickLinks.length > 0 ? (
      <div className="grid grid-cols-2 gap-2">
        {quickLinks.map((link) => {
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              onClick={onNavigate}
              className="flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center"
            >
              <Icon className={cn('w-4 h-4 mb-1', `text-${link.color}`)} />
              <span className="text-xs text-slate-muted">{link.label}</span>
            </Link>
          );
        })}
      </div>
    ) : null;

  return (
    <div className="space-y-4">
      {/* Mobile header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-slate-card border-b border-slate-border">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="w-8 h-8 rounded-lg bg-gradient-to-br from-teal-400 to-cyan-400 flex items-center justify-center shrink-0"
              title="Back to Home"
            >
              <Zap className="w-4 h-4 text-slate-900" />
            </Link>
            <div className="w-px h-6 bg-slate-border" />
            <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center shrink-0', colors.iconBg)}>
              <ModuleIcon className="w-4 h-4 text-slate-deep" />
            </div>
            <div className="flex flex-col">
              <span className="font-display font-bold text-white tracking-tight text-sm">{moduleName}</span>
              <span className="text-[9px] text-slate-muted uppercase tracking-widest">{moduleSubtitle}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {headerContent}
            <button
              onClick={openCommandPalette}
              className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
              title="Search"
            >
              <Search className="w-5 h-5" />
            </button>
            <button
              onClick={toggleTheme}
              className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
              title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
            <button
              onClick={() => setMobileMenuOpen((v) => !v)}
              className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Desktop top bar */}
      <div className="hidden lg:flex items-center justify-between bg-slate-card border border-slate-border rounded-xl px-4 py-3">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-slate-muted hover:text-white hover:bg-slate-elevated transition-colors"
            title="Back to Home"
          >
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-teal-400 to-cyan-400 flex items-center justify-center">
              <Zap className="w-4 h-4 text-slate-900" />
            </div>
            <span className="text-xs font-medium hidden xl:inline">BOS</span>
          </Link>
          <div className="w-px h-8 bg-slate-border" />
          <Link href={baseRoute} className="flex items-center gap-3 group">
            <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center shrink-0', colors.iconBg)}>
              <ModuleIcon className="w-5 h-5 text-slate-deep" />
            </div>
            <div className="flex flex-col">
              <span className="font-display font-bold text-white tracking-tight">{moduleName}</span>
              <span className="text-[10px] text-slate-muted uppercase tracking-widest">{moduleSubtitle}</span>
            </div>
          </Link>
        </div>
        <div className="flex items-center gap-2">
          {headerContent}
          <button
            onClick={openCommandPalette}
            className="flex items-center gap-2 px-3 py-1.5 bg-slate-elevated hover:bg-slate-border rounded-lg text-slate-muted hover:text-white transition-colors"
            title="Search (Cmd+K)"
          >
            <Search className="w-4 h-4" />
            <span className="text-sm hidden xl:inline">Search</span>
            <kbd className="hidden xl:inline text-xs bg-slate-border/50 px-1.5 py-0.5 rounded">⌘K</kbd>
          </button>
          <button
            onClick={toggleTheme}
            className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
            title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
          <div className="flex items-center gap-2">
            <div className={cn('p-2', colors.iconText)}>
              <User className="w-5 h-5" />
            </div>
            {isAuthenticated && (
              <button
                onClick={logout}
                className="p-2 text-slate-muted hover:text-coral-alert hover:bg-slate-elevated rounded-lg transition-colors"
                title="Sign out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div
          className="lg:hidden fixed inset-0 z-30 bg-black/40 backdrop-blur-sm"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Mobile drawer */}
      <div
        className={cn(
          'lg:hidden fixed top-[64px] bottom-0 left-0 z-40 w-72 max-w-[85vw] bg-slate-card border-r border-slate-border transform transition-transform duration-300 overflow-y-auto',
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="p-4 space-y-4">
          {renderQuickLinks(() => setMobileMenuOpen(false))}
          {renderNavSections(() => setMobileMenuOpen(false))}

          <div className="pt-3 border-t border-slate-border space-y-2">
            <button
              onClick={() => {
                toggleTheme();
              }}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 text-sm text-slate-muted transition-colors"
            >
              <span>{isDarkMode ? 'Light mode' : 'Dark mode'}</span>
              {isDarkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            {isAuthenticated && (
              <button
                onClick={() => {
                  logout();
                  setMobileMenuOpen(false);
                }}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-slate-elevated text-sm text-slate-muted hover:bg-slate-border/30 transition-colors"
                title="Sign out"
              >
                <span>Sign out</span>
                <LogOut className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6 pt-[64px] lg:pt-0">
        {/* Sidebar Navigation */}
        <aside className="hidden lg:block bg-slate-card border border-slate-border rounded-xl p-4 space-y-4 h-fit">
          {/* Header */}
          <div className="pb-3 border-b border-slate-border">
            <h1 className="text-lg font-semibold text-white">{sidebarTitle}</h1>
            <p className="text-slate-muted text-xs mt-1">{sidebarDescription}</p>
          </div>

          {/* Workflow Phase Indicator */}
          {workflowPhases && workflowPhases.length > 0 && (
            <div className="bg-slate-elevated rounded-lg p-3">
              <p className="text-xs text-slate-muted mb-2">Workflow Phase</p>
              <div className="flex items-center gap-1">
                {workflowPhases.map((phase, idx) => (
                  <div key={phase.key} className="flex items-center">
                    <div
                      className={cn(
                        'px-2 py-1 rounded text-xs font-medium transition-colors',
                        currentPhase === phase.key
                          ? `${colors.activeItemBg} ${colors.activeItemText} border ${colors.activeBorder}`
                          : 'text-slate-muted'
                      )}
                    >
                      {phase.label}
                    </div>
                    {idx < workflowPhases.length - 1 && (
                      <ChevronRight className="w-3 h-3 text-slate-muted mx-1" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Navigation Sections */}
          {renderNavSections()}

          {/* Quick Links */}
          {quickLinks && quickLinks.length > 0 && (
            <div className="pt-3 border-t border-slate-border">
              <p className="text-xs text-slate-muted mb-2 px-1">Quick Links</p>
              {renderQuickLinks()}
            </div>
          )}

          {/* Workflow Steps Guide */}
          {workflowSteps && workflowSteps.length > 0 && (
            <div className="pt-3 border-t border-slate-border">
              <p className="text-xs text-slate-muted mb-2 px-1">Workflow</p>
              <div className="space-y-1 text-[10px] text-slate-muted px-1">
                {workflowSteps.map((step, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <div
                      className={cn(
                        'w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold',
                        `bg-${step.color}-500/20 text-${step.color}-400`
                      )}
                    >
                      {idx + 1}
                    </div>
                    <span>{step.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>

        {/* Main Content */}
        <div className="space-y-6">{children}</div>
      </div>
    </div>
  );
}

export default ModuleLayout;
