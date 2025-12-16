'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
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
  ArrowRight,
  Star,
  Activity,
  Sun,
  Moon,
} from 'lucide-react';
import { useAuth, Scope } from '@/lib/auth-context';
import { useTheme } from '@dotmac/design-tokens';
import { applyColorScheme } from '@/lib/theme';
import { cn } from '@/lib/utils';

type ModuleCard = {
  key: string;
  name: string;
  description: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  accentColor: string;
  requiredScopes?: Scope[];
  stub?: boolean;
};

const MODULES: ModuleCard[] = [
  {
    key: 'hr',
    name: 'People',
    description: 'HR operations, payroll, leave, attendance, and workforce analytics.',
    href: '/hr',
    icon: Briefcase,
    badge: 'HR',
    accentColor: 'amber',
    requiredScopes: ['hr:read'],
  },
  {
    key: 'books',
    name: 'Books',
    description: 'Accounting hub with ledger, AR/AP, tax compliance, and controls.',
    href: '/books',
    icon: BookOpen,
    badge: 'Accounting',
    accentColor: 'teal',
    requiredScopes: ['analytics:read'],
  },
  {
    key: 'support',
    name: 'Support',
    description: 'Omnichannel helpdesk, tickets, SLAs, CSAT, and automation.',
    href: '/support',
    icon: LifeBuoy,
    badge: 'Helpdesk',
    accentColor: 'teal',
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
  },
  {
    key: 'purchasing',
    name: 'Purchasing',
    description: 'Vendor management, bills, purchase orders, and AP aging.',
    href: '/purchasing',
    icon: ShoppingCart,
    badge: 'AP',
    accentColor: 'violet',
    requiredScopes: ['analytics:read'],
  },
  {
    key: 'sales',
    name: 'Sales',
    description: 'Invoices, quotations, orders, and customer management.',
    href: '/sales',
    icon: Users,
    badge: 'AR',
    accentColor: 'emerald',
    requiredScopes: ['analytics:read'],
  },
  {
    key: 'analytics',
    name: 'Analytics',
    description: 'Cross-domain dashboards, reports, and business insights.',
    href: '/analytics',
    icon: LayoutDashboard,
    accentColor: 'cyan',
    stub: true,
    requiredScopes: ['analytics:read'],
  },
  {
    key: 'notifications',
    name: 'Notifications',
    description: 'Email, SMS, in-app digests and delivery logs.',
    href: '/notifications',
    icon: Bell,
    accentColor: 'rose',
    stub: true,
    requiredScopes: ['admin:read'],
  },
  {
    key: 'security',
    name: 'Controls',
    description: 'Access management, audit trails, and data protections.',
    href: '/admin/security',
    icon: ShieldCheck,
    accentColor: 'slate',
    stub: true,
    requiredScopes: ['admin:read'],
  },
];

const ACCENT_STYLES: Record<string, { bg: string; border: string; text: string; icon: string }> = {
  amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', icon: 'from-amber-400 to-amber-300' },
  teal: { bg: 'bg-teal-500/10', border: 'border-teal-500/30', text: 'text-teal-400', icon: 'from-teal-400 to-teal-300' },
  sky: { bg: 'bg-sky-500/10', border: 'border-sky-500/30', text: 'text-sky-400', icon: 'from-sky-400 to-sky-300' },
  violet: { bg: 'bg-violet-500/10', border: 'border-violet-500/30', text: 'text-violet-400', icon: 'from-violet-400 to-violet-300' },
  emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', icon: 'from-emerald-400 to-emerald-300' },
  cyan: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/30', text: 'text-cyan-400', icon: 'from-cyan-400 to-cyan-300' },
  rose: { bg: 'bg-rose-500/10', border: 'border-rose-500/30', text: 'text-rose-400', icon: 'from-rose-400 to-rose-300' },
  slate: { bg: 'bg-slate-500/10', border: 'border-slate-500/30', text: 'text-slate-400', icon: 'from-slate-400 to-slate-300' },
};

const DEFAULT_KEY = 'dotmac_default_module';

export default function HomePage() {
  const router = useRouter();
  const { hasAnyScope, isLoading } = useAuth();
  const { isDarkMode, setColorScheme } = useTheme();
  const [defaultModuleKey, setDefaultModuleKey] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(DEFAULT_KEY);
  });
  const hasRedirected = useRef(false);

  const toggleTheme = () => {
    const next = isDarkMode ? 'light' : 'dark';
    setColorScheme(next);
    applyColorScheme(next);
  };

  const accessibleModules = useMemo(
    () =>
      MODULES.filter(module => {
        if (!module.requiredScopes) return true;
        return hasAnyScope(module.requiredScopes);
      }),
    [hasAnyScope],
  );

  useEffect(() => {
    if (isLoading || hasRedirected.current) return;
    if (!defaultModuleKey) return;

    const target = accessibleModules.find(m => m.key === defaultModuleKey);
    if (target && !target.stub) {
      hasRedirected.current = true;
      router.replace(target.href);
    }
  }, [accessibleModules, defaultModuleKey, isLoading, router]);

  const handleSetDefault = (key: string) => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(DEFAULT_KEY, key);
    setDefaultModuleKey(key);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-teal-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-deep">
      {/* Header */}
      <header className="border-b border-slate-border bg-slate-card">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-400 to-teal-300 flex items-center justify-center">
              <Activity className="w-6 h-6 text-slate-900" />
            </div>
            <div className="flex flex-col">
              <span className="font-display font-bold text-white tracking-tight text-lg">Dotmac</span>
              <span className="text-[10px] text-slate-muted uppercase tracking-widest">Insights Platform</span>
            </div>
          </div>
          <button
            onClick={toggleTheme}
            className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
            title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-10">
        <div className="flex flex-col gap-3 mb-10">
          <div className="flex items-center gap-2 text-sm font-medium text-teal-400">
            <Star className="w-4 h-4" />
            Choose your workspace
          </div>
          <h1 className="text-3xl font-semibold text-white">Where do you want to work today?</h1>
          <p className="text-slate-muted max-w-2xl">
            Jump into a specialist module. Set a default to skip this chooser next time.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {accessibleModules.map(module => {
            const Icon = module.icon;
            const isDefault = defaultModuleKey === module.key;
            const accent = ACCENT_STYLES[module.accentColor] || ACCENT_STYLES.teal;

            return (
              <div
                key={module.key}
                className={cn(
                  'group rounded-2xl border bg-slate-card p-5 flex flex-col gap-4 transition-all',
                  isDefault ? `${accent.border} ${accent.bg}` : 'border-slate-border hover:border-slate-border/80'
                )}
              >
                <div className="flex items-center gap-3">
                  <div className={cn('w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center', accent.icon)}>
                    <Icon className="w-5 h-5 text-slate-900" />
                  </div>
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <h2 className="text-lg font-semibold text-white">{module.name}</h2>
                      {module.badge && (
                        <span className={cn('text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full', accent.bg, accent.text)}>
                          {module.badge}
                        </span>
                      )}
                    </div>
                    {isDefault && (
                      <span className={cn('text-xs font-medium', accent.text)}>Default workspace</span>
                    )}
                  </div>
                </div>

                <p className="text-sm text-slate-muted flex-1">{module.description}</p>

                <div className="flex items-center gap-3">
                  {module.stub ? (
                    <span className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-xl bg-slate-elevated text-slate-muted cursor-not-allowed">
                      Coming soon
                    </span>
                  ) : (
                    <Link
                      href={module.href}
                      className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-xl text-white bg-slate-elevated hover:bg-slate-border transition-colors"
                    >
                      Open
                      <ArrowRight className="w-4 h-4" />
                    </Link>
                  )}
                  {!module.stub && (
                    <button
                      onClick={() => handleSetDefault(module.key)}
                      className={cn(
                        'text-sm font-medium rounded-xl px-3 py-2 border transition-colors',
                        isDefault
                          ? `${accent.border} ${accent.bg} ${accent.text}`
                          : 'border-slate-border text-slate-muted hover:border-slate-muted hover:text-white'
                      )}
                    >
                      {isDefault ? 'Default' : 'Set default'}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </main>
    </div>
  );
}
