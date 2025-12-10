'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Users,
  Radio,
  TrendingUp,
  Database,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Activity,
  Menu,
  X,
  Lightbulb,
  Lock,
  Sun,
  Moon,
  User,
  LogOut,
  Key,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSyncStatus } from '@/hooks/useApi';
import { useAuth, Scope } from '@/lib/auth-context';
import { useTheme } from '@dotmac/design-tokens';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string | number;
  requiredScopes?: Scope[];
}

const navigation: NavItem[] = [
  { name: 'Overview', href: '/', icon: LayoutDashboard },
  { name: 'Customers', href: '/customers', icon: Users, requiredScopes: ['customers:read'] },
  { name: 'POPs', href: '/pops', icon: Radio, requiredScopes: ['analytics:read'] },
  { name: 'Analytics', href: '/analytics', icon: TrendingUp, requiredScopes: ['analytics:read'] },
  { name: 'Insights', href: '/insights', icon: Lightbulb, requiredScopes: ['analytics:read'] },
  { name: 'Data Explorer', href: '/explorer', icon: Database, requiredScopes: ['explore:read'] },
  { name: 'Sync', href: '/sync', icon: RefreshCw, requiredScopes: ['sync:read'] },
];

// Keys in sync status response that represent actual sync sources (have .status property)
const SYNC_SOURCE_KEYS = ['splynx', 'erpnext', 'chatwoot'] as const;

function ThemeToggle({ collapsed }: { collapsed?: boolean }) {
  const { isDarkMode, setColorScheme } = useTheme();

  return (
    <button
      onClick={() => setColorScheme(isDarkMode ? 'light' : 'dark')}
      className={cn(
        'flex items-center justify-center rounded-lg text-slate-muted hover:text-foreground hover:bg-slate-elevated transition-colors',
        collapsed ? 'w-10 h-10' : 'w-full px-3 py-2 gap-2'
      )}
      title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDarkMode ? (
        <>
          <Sun className="w-5 h-5" />
          {!collapsed && <span className="text-sm">Light Mode</span>}
        </>
      ) : (
        <>
          <Moon className="w-5 h-5" />
          {!collapsed && <span className="text-sm">Dark Mode</span>}
        </>
      )}
    </button>
  );
}

function SyncStatusIndicator() {
  const { data: status, error } = useSyncStatus();

  if (error) {
    return (
      <div className="flex items-center gap-2 text-coral-alert text-xs">
        <span className="w-2 h-2 rounded-full bg-coral-alert" />
        <span>Disconnected</span>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="flex items-center gap-2 text-slate-muted text-xs">
        <span className="w-2 h-2 rounded-full bg-slate-muted animate-pulse" />
        <span>Checking...</span>
      </div>
    );
  }

  // Filter to only sync source entries (exclude celery_enabled, celery_workers, etc.)
  const syncSources = SYNC_SOURCE_KEYS
    .filter((key) => status[key] && typeof status[key] === 'object' && 'status' in status[key])
    .map((key) => status[key]);

  const allSynced = syncSources.length === 0 || syncSources.every(
    (s) => s && (s.status === 'completed' || s.status === 'never_synced')
  );

  return (
    <div className={cn(
      'flex items-center gap-2 text-xs',
      allSynced ? 'text-teal-electric' : 'text-amber-warn'
    )}>
      <span className={cn(
        'w-2 h-2 rounded-full',
        allSynced ? 'bg-teal-electric' : 'bg-amber-warn animate-pulse'
      )} />
      <span>{allSynced ? 'Synced' : 'Syncing...'}</span>
    </div>
  );
}

function AuthStatusIndicator({ collapsed }: { collapsed?: boolean }) {
  const { isAuthenticated, isLoading, scopes, logout } = useAuth();
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [tokenValue, setTokenValue] = useState('');

  const handleSetToken = () => {
    if (tokenValue.trim()) {
      localStorage.setItem('dotmac_access_token', tokenValue.trim());
      setTokenValue('');
      setShowTokenInput(false);
      // Trigger auth check by dispatching storage event (for cross-tab sync)
      window.dispatchEvent(new StorageEvent('storage', { key: 'dotmac_access_token' }));
      window.location.reload();
    }
  };

  if (isLoading) {
    return (
      <div className={cn(
        'flex items-center text-slate-muted text-xs',
        collapsed ? 'justify-center' : 'gap-2 px-3'
      )}>
        <span className="w-2 h-2 rounded-full bg-slate-muted animate-pulse" />
        {!collapsed && <span>Checking auth...</span>}
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className={cn('text-xs', collapsed && 'flex justify-center')}>
        {showTokenInput ? (
          <div className="px-3 space-y-2">
            <input
              type="password"
              value={tokenValue}
              onChange={(e) => setTokenValue(e.target.value)}
              placeholder="Paste JWT token..."
              className="w-full px-2 py-1.5 bg-slate-elevated border border-slate-border rounded text-white text-xs placeholder:text-slate-muted focus:outline-none focus:border-teal-electric"
              onKeyDown={(e) => e.key === 'Enter' && handleSetToken()}
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={handleSetToken}
                className="flex-1 px-2 py-1 bg-teal-electric text-slate-deep rounded text-xs font-medium hover:bg-teal-glow transition-colors"
              >
                Set Token
              </button>
              <button
                onClick={() => { setShowTokenInput(false); setTokenValue(''); }}
                className="px-2 py-1 text-slate-muted hover:text-white transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowTokenInput(true)}
            className={cn(
              'flex items-center rounded-lg text-amber-warn hover:text-amber-warn/80 hover:bg-slate-elevated transition-colors',
              collapsed ? 'justify-center p-2' : 'gap-2 px-3 py-2 w-full'
            )}
            title="Set authentication token"
          >
            <Key className="w-4 h-4" />
            {!collapsed && <span>Set Token</span>}
          </button>
        )}
      </div>
    );
  }

  // Authenticated state
  const scopeCount = scopes.length;
  const isDevMode = process.env.NODE_ENV === 'development';

  return (
    <div className={cn('text-xs', collapsed && 'flex flex-col items-center gap-2')}>
      {/* User status */}
      <div className={cn(
        'flex items-center text-teal-electric',
        collapsed ? 'justify-center' : 'gap-2 px-3'
      )}>
        <User className="w-4 h-4" />
        {!collapsed && (
          <span>
            {isDevMode ? 'Dev Token' : 'Authenticated'}
            {scopeCount > 0 && <span className="text-slate-muted ml-1">({scopeCount} scopes)</span>}
          </span>
        )}
      </div>

      {/* Logout button */}
      {!isDevMode && (
        <button
          onClick={logout}
          className={cn(
            'flex items-center rounded-lg text-slate-muted hover:text-coral-alert hover:bg-slate-elevated transition-colors mt-1',
            collapsed ? 'justify-center p-2' : 'gap-2 px-3 py-1.5 w-full'
          )}
          title="Sign out"
        >
          <LogOut className="w-4 h-4" />
          {!collapsed && <span>Sign Out</span>}
        </button>
      )}
    </div>
  );
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const { hasAnyScope, isAuthenticated } = useAuth();

  // Filter navigation items based on user scopes
  const filteredNavigation = useMemo(() => {
    return navigation.map((item) => {
      // If no scopes required, item is accessible
      if (!item.requiredScopes || item.requiredScopes.length === 0) {
        return { ...item, accessible: true };
      }
      // Check if user has any of the required scopes
      const accessible = isAuthenticated && hasAnyScope(item.requiredScopes);
      return { ...item, accessible };
    });
  }, [isAuthenticated, hasAnyScope]);

  // Load saved preference after hydration (avoids SSR mismatch)
  useEffect(() => {
    const saved = localStorage.getItem('sidebar_collapsed');
    if (saved) setCollapsed(JSON.parse(saved));
    setHydrated(true);
  }, []);

  // Persist collapsed state only after initial hydration
  useEffect(() => {
    if (hydrated) {
      localStorage.setItem('sidebar_collapsed', JSON.stringify(collapsed));
    }
  }, [collapsed, hydrated]);

  return (
    <div className="min-h-screen bg-slate-deep">
      {/* Mobile header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-slate-card border-b border-slate-border">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-teal-electric to-teal-glow flex items-center justify-center">
              <Activity className="w-5 h-5 text-slate-deep" />
            </div>
            <span className="font-display font-bold text-white">Dotmac</span>
          </div>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 text-slate-muted hover:text-white transition-colors"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <div className={cn(
        'lg:hidden fixed top-14 left-0 bottom-0 z-40 w-64 bg-slate-card border-r border-slate-border transform transition-transform duration-300',
        mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        <nav className="p-4 space-y-1">
          {filteredNavigation.map((item) => {
            const isActive = pathname === item.href;

            // For inaccessible items, show disabled state with lock icon
            if (!item.accessible) {
              return (
                <div
                  key={item.name}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-muted/50 cursor-not-allowed"
                  title="You don't have permission to access this section"
                >
                  <item.icon className="w-5 h-5" />
                  <span className="font-medium flex-1">{item.name}</span>
                  <Lock className="w-4 h-4" />
                </div>
              );
            }

            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
                  isActive
                    ? 'bg-teal-electric/10 text-teal-electric'
                    : 'text-slate-muted hover:text-white hover:bg-slate-elevated'
                )}
              >
                <item.icon className="w-5 h-5" />
                <span className="font-medium">{item.name}</span>
              </Link>
            );
          })}
        </nav>
        {/* Mobile bottom controls */}
        <div className="absolute bottom-4 left-4 right-4 space-y-3">
          <AuthStatusIndicator collapsed={false} />
          <ThemeToggle collapsed={false} />
        </div>
      </div>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          'hidden lg:flex fixed left-0 top-0 bottom-0 z-40 flex-col bg-slate-card border-r border-slate-border transition-all duration-300',
          collapsed ? 'w-16' : 'w-64'
        )}
      >
        {/* Logo */}
        <div className={cn(
          'flex items-center h-16 border-b border-slate-border px-4',
          collapsed ? 'justify-center' : 'gap-3'
        )}>
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-teal-electric to-teal-glow flex items-center justify-center shrink-0 glow-teal">
            <Activity className="w-5 h-5 text-slate-deep" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-display font-bold text-white tracking-tight">Dotmac</span>
              <span className="text-[10px] text-slate-muted uppercase tracking-widest">Insights</span>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {filteredNavigation.map((item) => {
            const isActive = pathname === item.href;

            // For inaccessible items, show disabled state with lock icon
            if (!item.accessible) {
              return (
                <div
                  key={item.name}
                  className={cn(
                    'group flex items-center rounded-lg relative cursor-not-allowed',
                    collapsed ? 'justify-center p-3' : 'gap-3 px-3 py-2.5',
                    'text-slate-muted/50'
                  )}
                  title="You don't have permission to access this section"
                >
                  <item.icon className="w-5 h-5 shrink-0" />
                  {!collapsed && (
                    <>
                      <span className="font-medium flex-1">{item.name}</span>
                      <Lock className="w-4 h-4" />
                    </>
                  )}

                  {/* Tooltip for collapsed state */}
                  {collapsed && (
                    <div className="absolute left-full ml-2 px-2 py-1 bg-slate-elevated border border-slate-border rounded text-sm text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50 flex items-center gap-2">
                      <Lock className="w-3 h-3" />
                      {item.name}
                    </div>
                  )}
                </div>
              );
            }

            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  'group flex items-center rounded-lg transition-all duration-200 relative',
                  collapsed ? 'justify-center p-3' : 'gap-3 px-3 py-2.5',
                  isActive
                    ? 'bg-teal-electric/10 text-teal-electric'
                    : 'text-slate-muted hover:text-white hover:bg-slate-elevated'
                )}
              >
                <item.icon className={cn('w-5 h-5 shrink-0', isActive && 'drop-shadow-[0_0_8px_rgba(0,212,170,0.5)]')} />
                {!collapsed && <span className="font-medium">{item.name}</span>}
                {isActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-teal-electric rounded-r-full" />
                )}

                {/* Tooltip for collapsed state */}
                {collapsed && (
                  <div className="absolute left-full ml-2 px-2 py-1 bg-slate-elevated border border-slate-border rounded text-sm text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                    {item.name}
                  </div>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Bottom section */}
        <div className={cn(
          'border-t border-slate-border p-3',
          collapsed && 'flex flex-col items-center'
        )}>
          {/* Auth status */}
          <div className="mb-3">
            <AuthStatusIndicator collapsed={collapsed} />
          </div>

          {/* Sync status */}
          {!collapsed && (
            <div className="mb-3 px-3">
              <SyncStatusIndicator />
            </div>
          )}

          {/* Theme toggle */}
          <div className="mb-2">
            <ThemeToggle collapsed={collapsed} />
          </div>

          {/* Collapse button */}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={cn(
              'flex items-center justify-center rounded-lg text-slate-muted hover:text-white hover:bg-slate-elevated transition-colors',
              collapsed ? 'w-10 h-10' : 'w-full px-3 py-2 gap-2'
            )}
          >
            {collapsed ? (
              <ChevronRight className="w-5 h-5" />
            ) : (
              <>
                <ChevronLeft className="w-5 h-5" />
                <span className="text-sm">Collapse</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main
        className={cn(
          'min-h-screen transition-all duration-300 pt-14 lg:pt-0',
          collapsed ? 'lg:ml-16' : 'lg:ml-64'
        )}
      >
        <div className="p-4 lg:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
