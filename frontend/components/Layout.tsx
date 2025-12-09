'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Users,
  Radio,
  TrendingUp,
  Database,
  RefreshCw,
  Settings,
  ChevronLeft,
  ChevronRight,
  Activity,
  Menu,
  X,
  KeyRound,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSyncStatus } from '@/hooks/useApi';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string | number;
}

const navigation: NavItem[] = [
  { name: 'Overview', href: '/', icon: LayoutDashboard },
  { name: 'Customers', href: '/customers', icon: Users },
  { name: 'POPs', href: '/pops', icon: Radio },
  { name: 'Analytics', href: '/analytics', icon: TrendingUp },
  { name: 'Data Explorer', href: '/explorer', icon: Database },
  { name: 'Sync', href: '/sync', icon: RefreshCw },
];

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

  const allSynced = Object.values(status).every(
    (s) => s.status === 'completed' || s.status === 'never_synced'
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

function ApiKeyControl({ collapsed }: { collapsed: boolean }) {
  const [value, setValue] = useState('');
  const [saved, setSaved] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'saved' | 'cleared'>('idle');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem('dotmac_api_key');
    if (stored) {
      setSaved(stored);
      setValue(stored);
    }
  }, []);

  const handleSave = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    localStorage.setItem('dotmac_api_key', trimmed);
    setSaved(trimmed);
    setStatus('saved');
    setTimeout(() => setStatus('idle'), 1800);
  };

  const handleClear = () => {
    localStorage.removeItem('dotmac_api_key');
    setSaved(null);
    setValue('');
    setStatus('cleared');
    setTimeout(() => setStatus('idle'), 1800);
  };

  if (!mounted) return null;

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-2 text-slate-muted text-[10px]">
        <div className="p-2 rounded-lg bg-slate-elevated border border-slate-border">
          <KeyRound className="w-4 h-4" />
        </div>
        <span>API Key</span>
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border border-slate-border bg-slate-elevated p-3">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-md bg-teal-electric/10 flex items-center justify-center">
          <KeyRound className="w-4 h-4 text-teal-electric" />
        </div>
        <div className="leading-tight">
          <p className="text-xs font-semibold text-white">API Key</p>
          <p className="text-[11px] text-slate-muted">Used for all backend requests (X-API-Key)</p>
        </div>
      </div>
      <input
        type="password"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Enter API key"
        className="w-full rounded-md border border-slate-border bg-slate-card px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:border-teal-electric"
      />
      <div className="flex items-center justify-between gap-2">
        <button
          onClick={handleSave}
          className="flex-1 rounded-md bg-teal-electric text-slate-deep text-sm font-semibold py-2 hover:bg-teal-glow transition-colors"
          disabled={!value.trim()}
        >
          Save
        </button>
        <button
          onClick={handleClear}
          className="px-3 py-2 rounded-md border border-slate-border text-slate-muted text-sm hover:text-white hover:border-slate-muted transition-colors"
          disabled={!saved}
        >
          Clear
        </button>
      </div>
      <div className="text-[11px] text-slate-muted flex items-center gap-2">
        <span className={cn(
          'w-2 h-2 rounded-full',
          status === 'saved' ? 'bg-teal-electric' : status === 'cleared' ? 'bg-slate-muted' : saved ? 'bg-teal-electric' : 'bg-slate-muted'
        )} />
        <span>
          {status === 'saved' && 'Saved locally'}
          {status === 'cleared' && 'Cleared'}
          {status === 'idle' && (saved ? `Using ${saved.slice(0, 4)}…` : 'Not set')}
        </span>
      </div>
    </div>
  );
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem('sidebar_collapsed');
    if (saved) setCollapsed(JSON.parse(saved));
  }, []);

  useEffect(() => {
    localStorage.setItem('sidebar_collapsed', JSON.stringify(collapsed));
  }, [collapsed]);

  if (!mounted) return null;

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
          {navigation.map((item) => {
            const isActive = pathname === item.href;
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
          {navigation.map((item) => {
            const isActive = pathname === item.href;
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
          {/* Sync status */}
          {!collapsed && (
            <div className="mb-3 px-3">
              <SyncStatusIndicator />
            </div>
          )}

          <div className="mb-3 px-3">
            <ApiKeyControl collapsed={collapsed} />
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
