'use client';

import Link from 'next/link';
import { Sun, Moon, User, LogOut, Zap, Search, LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useModuleLayoutContext } from './context';

// =============================================================================
// PROPS
// =============================================================================

interface ModuleHeaderProps {
  /** Module display name */
  moduleName: string;
  /** Module subtitle */
  moduleSubtitle: string;
  /** Module icon component */
  icon: LucideIcon;
  /** Optional header content (e.g., live metrics) */
  headerContent?: React.ReactNode;
}

// =============================================================================
// COMPONENT
// =============================================================================

/**
 * Desktop top bar with branding, search, and user actions
 */
export function ModuleHeader({ moduleName, moduleSubtitle, icon: ModuleIcon, headerContent }: ModuleHeaderProps) {
  const { colors, baseRoute, isDarkMode, isAuthenticated, toggleTheme, logout, openCommandPalette } =
    useModuleLayoutContext();

  return (
    <div className="hidden lg:flex items-center justify-between bg-slate-card border border-slate-border rounded-xl px-4 py-3">
      <div className="flex items-center gap-4">
        {/* App Home Link */}
        <Link
          href="/"
          className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-slate-muted hover:text-foreground hover:bg-slate-elevated transition-colors"
          title="Back to app home"
        >
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-teal-400 to-cyan-400 flex items-center justify-center">
            <Zap className="w-4 h-4 text-slate-900" />
          </div>
          <span className="text-xs font-medium hidden xl:inline">BOS</span>
        </Link>

        <div className="w-px h-8 bg-slate-border" />

        {/* Module Home Link */}
        <Link href={baseRoute} className="flex items-center gap-3 group">
          <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center shrink-0', colors.iconBg)}>
            <ModuleIcon className="w-5 h-5 text-slate-deep" />
          </div>
          <div className="flex flex-col">
            <span className="font-display font-bold text-foreground tracking-tight">{moduleName}</span>
            <span className="text-[10px] text-slate-muted uppercase tracking-widest">{moduleSubtitle}</span>
          </div>
        </Link>
      </div>

      <div className="flex items-center gap-2">
        {headerContent}

        {/* Search Button */}
        <button
          onClick={openCommandPalette}
          className="flex items-center gap-2 px-3 py-1.5 bg-slate-elevated hover:bg-slate-border rounded-lg text-slate-muted hover:text-foreground transition-colors"
          title="Search (Cmd+K)"
        >
          <Search className="w-4 h-4" />
          <span className="text-sm hidden xl:inline">Search</span>
          <kbd className="hidden xl:inline text-xs bg-slate-border/50 px-1.5 py-0.5 rounded">&#x2318;K</kbd>
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
          title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>

        {/* User Actions */}
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
  );
}
