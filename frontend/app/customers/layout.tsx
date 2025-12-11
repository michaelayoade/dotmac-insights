'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  Users,
  UserMinus,
  TrendingUp,
  Lightbulb,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

const customerTabs = [
  { key: 'list', label: 'All Customers', href: '/customers', icon: Users },
  { key: 'analytics', label: 'Analytics', href: '/customers/analytics', icon: TrendingUp },
  { key: 'insights', label: 'Insights', href: '/customers/insights', icon: Lightbulb },
];

export default function CustomersLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope(['customers:read', 'analytics:read']);
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
      {/* Navigation Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-slate-border pb-4">
        {customerTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = pathname === tab.href ||
            (tab.key === 'list' && pathname === '/customers') ||
            (tab.key !== 'list' && pathname.startsWith(tab.href));
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
