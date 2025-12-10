'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  Database,
  Users,
  HeartPulse,
  Network,
  AlertTriangle,
} from 'lucide-react';

const insightsTabs = [
  { key: 'overview', label: 'Overview', href: '/insights/overview', icon: LayoutDashboard },
  { key: 'completeness', label: 'Data Completeness', href: '/insights/completeness', icon: Database },
  { key: 'segments', label: 'Customer Segments', href: '/insights/segments', icon: Users },
  { key: 'health', label: 'Customer Health', href: '/insights/health', icon: HeartPulse },
  { key: 'relationships', label: 'Data Relationships', href: '/insights/relationships', icon: Network },
  { key: 'anomalies', label: 'Anomalies', href: '/insights/anomalies', icon: AlertTriangle },
];

export default function InsightsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-display text-3xl font-bold text-white">Deep Insights</h1>
        <p className="text-slate-muted mt-1">
          Analyze data completeness, relationships, and identify actionable insights
        </p>
      </div>

      {/* Navigation Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-slate-border pb-4">
        {insightsTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = pathname === tab.href || (pathname === '/insights' && tab.key === 'overview');
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
