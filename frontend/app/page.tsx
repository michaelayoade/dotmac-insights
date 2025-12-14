'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
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
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';

type ModuleCard = {
  key: string;
  name: string;
  description: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  requiredScopes?: string[];
  stub?: boolean;
};

const MODULES: ModuleCard[] = [
  {
    key: 'hr',
    name: 'HR',
    description: 'People ops, payroll, leave, attendance, analytics.',
    href: '/hr',
    icon: Briefcase,
    badge: 'Specialist',
    requiredScopes: ['hr:read'],
  },
  {
    key: 'books',
    name: 'Books',
    description: 'Accounting hub with ledger, AR/AP, tax, controls.',
    href: '/books',
    icon: BookOpen,
    badge: 'Specialist',
    requiredScopes: ['analytics:read'],
  },
  {
    key: 'support',
    name: 'Support',
    description: 'Tickets, SLAs, CSAT, and customer conversations.',
    href: '/support',
    icon: LifeBuoy,
    badge: 'Specialist',
  },
  {
    key: 'inventory',
    name: 'Inventory',
    description: 'Stock, warehouses, valuation, and landed costs.',
    href: '/inventory',
    icon: ShoppingCart,
    stub: true,
    requiredScopes: ['analytics:read'],
  },
  {
    key: 'banking',
    name: 'Banking',
    description: 'Bank accounts, transactions, reconciliations.',
    href: '/banking',
    icon: Wallet2,
    stub: true,
    requiredScopes: ['analytics:read'],
  },
  {
    key: 'analytics',
    name: 'Analytics',
    description: 'Cross-domain dashboards and insights.',
    href: '/analytics',
    icon: LayoutDashboard,
    stub: true,
    requiredScopes: ['analytics:read'],
  },
  {
    key: 'notifications',
    name: 'Notifications',
    description: 'Email, SMS, in-app digests and delivery logs.',
    href: '/notifications',
    icon: Bell,
    stub: true,
    requiredScopes: ['admin:read'],
  },
  {
    key: 'security',
    name: 'Controls',
    description: 'Access, audit trails, and data protections.',
    href: '/support/security',
    icon: ShieldCheck,
    stub: true,
    requiredScopes: ['admin:read'],
  },
];

const DEFAULT_KEY = 'dotmac_default_module';

export default function HomePage() {
  const router = useRouter();
  const { hasAnyScope, isLoading } = useAuth();
  const [defaultModuleKey, setDefaultModuleKey] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(DEFAULT_KEY);
  });
  const hasRedirected = useRef(false);

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
    if (target) {
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
      <div className="min-h-[80vh] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-teal-electric border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-[80vh] px-6 py-10 lg:px-10">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col gap-3 mb-10">
          <div className="flex items-center gap-2 text-sm font-medium text-teal-electric">
            <Star className="w-4 h-4" />
            Choose your workspace
          </div>
          <h1 className="text-3xl font-semibold text-slate-900">Where do you want to work today?</h1>
          <p className="text-slate-600 max-w-2xl">
            Jump into a specialist module or the core customer workspace. Set a default to skip this chooser next time.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {accessibleModules.map(module => {
            const Icon = module.icon;
            const isDefault = defaultModuleKey === module.key;
            return (
              <div
                key={module.key}
                className="group rounded-2xl border border-slate-100 bg-white shadow-sm hover:shadow-md transition-all p-5 flex flex-col gap-4"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-50 to-white border border-teal-100 flex items-center justify-center text-teal-electric">
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <h2 className="text-lg font-semibold text-slate-900">{module.name}</h2>
                      {module.badge && (
                        <span className="text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                          {module.badge}
                        </span>
                      )}
                    </div>
                    {isDefault && (
                      <span className="text-xs text-teal-electric font-medium">Default</span>
                    )}
                  </div>
                </div>

                <p className="text-sm text-slate-600 flex-1">{module.description}</p>

                <div className="flex items-center gap-3">
          <button
            onClick={() => !module.stub && router.push(module.href)}
            className={`inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-xl transition-colors ${
              module.stub
                ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                : 'text-white bg-slate-900 hover:bg-slate-800'
            }`}
            disabled={module.stub}
          >
            {module.stub ? 'Coming soon' : 'Open'}
            {!module.stub && <ArrowRight className="w-4 h-4" />}
          </button>
                  <button
                    onClick={() => handleSetDefault(module.key)}
                    className={`text-sm font-medium rounded-xl px-3 py-2 border transition-colors ${
                      isDefault
                        ? 'border-teal-200 bg-teal-50 text-teal-electric'
                        : 'border-slate-200 text-slate-700 hover:border-slate-300'
                    }`}
                  >
                    {isDefault ? 'Default set' : 'Set default'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
