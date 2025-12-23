'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Sun, Moon, LogOut, Menu, X, Zap, Search, LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useModuleLayoutContext } from './context';
import { NavSectionsList } from './NavSection';
import { QuickLinksGrid } from './QuickLinks';
import type { QuickLink } from './types';

// =============================================================================
// PROPS
// =============================================================================

interface MobileNavProps {
  /** Module display name */
  moduleName: string;
  /** Module subtitle */
  moduleSubtitle: string;
  /** Module icon component */
  icon: LucideIcon;
  /** Optional quick links */
  quickLinks?: QuickLink[];
  /** Optional header content (e.g., live metrics) */
  headerContent?: React.ReactNode;
}

// =============================================================================
// COMPONENT
// =============================================================================

/**
 * Mobile navigation with header and slide-out drawer
 */
export function MobileNav({
  moduleName,
  moduleSubtitle,
  icon: ModuleIcon,
  quickLinks,
  headerContent,
}: MobileNavProps) {
  const { colors, baseRoute, isDarkMode, isAuthenticated, toggleTheme, logout, openCommandPalette } =
    useModuleLayoutContext();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const closeMenu = () => setMobileMenuOpen(false);

  return (
    <>
      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-slate-card border-b border-slate-border">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="w-8 h-8 rounded-lg bg-gradient-to-br from-teal-400 to-cyan-400 flex items-center justify-center shrink-0"
              title="Back to app home"
            >
              <Zap className="w-4 h-4 text-slate-900" />
            </Link>
            <div className="w-px h-6 bg-slate-border" />
            <Link
              href={baseRoute}
              className="flex items-center gap-3 group"
              title="Back to module home"
            >
              <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center shrink-0', colors.iconBg)}>
                <ModuleIcon className="w-4 h-4 text-slate-deep" />
              </div>
              <div className="flex flex-col">
                <span className="font-display font-bold text-foreground tracking-tight text-sm">{moduleName}</span>
                <span className="text-[9px] text-slate-muted uppercase tracking-widest">{moduleSubtitle}</span>
              </div>
            </Link>
          </div>
          <div className="flex items-center gap-2">
            {headerContent}
            <button
              onClick={openCommandPalette}
              className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
              title="Search"
            >
              <Search className="w-5 h-5" />
            </button>
            <button
              onClick={toggleTheme}
              className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
              title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
            <button
              onClick={() => setMobileMenuOpen((v) => !v)}
              className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Overlay */}
      {mobileMenuOpen && (
        <div
          className="lg:hidden fixed inset-0 z-30 bg-black/40 backdrop-blur-sm"
          onClick={closeMenu}
        />
      )}

      {/* Mobile Drawer */}
      <div
        className={cn(
          'lg:hidden fixed top-[64px] bottom-0 left-0 z-40 w-72 max-w-[85vw] bg-slate-card border-r border-slate-border transform transition-transform duration-300 overflow-y-auto',
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="p-4 space-y-4">
          {quickLinks && <QuickLinksGrid links={quickLinks} onNavigate={closeMenu} />}
          <NavSectionsList onNavigate={closeMenu} />

          <div className="pt-3 border-t border-slate-border space-y-2">
            <button
              onClick={toggleTheme}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 text-sm text-slate-muted transition-colors"
            >
              <span>{isDarkMode ? 'Light mode' : 'Dark mode'}</span>
              {isDarkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            {isAuthenticated && (
              <button
                onClick={() => {
                  logout();
                  closeMenu();
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
    </>
  );
}
