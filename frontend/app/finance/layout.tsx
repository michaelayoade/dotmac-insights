'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  FileText,
  CreditCard,
  Receipt,
  TrendingUp,
  Clock,
  Lightbulb,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

const financeTabs = [
  { key: 'dashboard', label: 'Dashboard', href: '/finance', icon: LayoutDashboard },
  { key: 'invoices', label: 'Invoices', href: '/finance/invoices', icon: FileText },
  { key: 'payments', label: 'Payments', href: '/finance/payments', icon: CreditCard },
  { key: 'credit-notes', label: 'Credit Notes', href: '/finance/credit-notes', icon: Receipt },
  { key: 'analytics', label: 'Analytics', href: '/finance/analytics', icon: TrendingUp },
  { key: 'insights', label: 'Insights', href: '/finance/insights', icon: Lightbulb },
];

export default function FinanceLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');
  const pathname = usePathname();

  if (authLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-electric" />
      </div>
    );
  }

  if (!hasAccess) {
    return <AccessDenied />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-display text-3xl font-bold text-white">Finance</h1>
        <p className="text-slate-muted mt-1">
          Track revenue, invoices, payments, and financial health
        </p>
      </div>

      {/* Navigation Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-slate-border pb-4">
        {financeTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = pathname === tab.href || (pathname === '/finance' && tab.key === 'dashboard');
          return (
            <Link
              key={tab.key}
              href={tab.href}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                isActive
                  ? 'bg-teal-electric/20 text-teal-electric border border-teal-electric/30'
                  : 'text-slate-muted hover:text-white hover:bg-slate-elevated'
              )}
            >
              <Icon className="w-4 h-4" />
              <span className="hidden sm:inline">{tab.label}</span>
            </Link>
          );
        })}
      </div>

      {/* Page Content */}
      {children}
    </div>
  );
}
