'use client';

import { Activity, DollarSign, ShoppingCart, Headphones, AlertTriangle, Server } from 'lucide-react';
import { ModuleLayout } from '@/components/ModuleLayout';
import type { NavSectionType as NavSection } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'Cross-module KPIs',
    icon: Activity,
    items: [
      { name: 'Overview', href: '/analytics', description: 'All metrics at a glance' },
    ],
  },
  {
    key: 'revenue',
    label: 'Revenue',
    description: 'Financial performance',
    icon: DollarSign,
    items: [
      { name: 'Revenue Trends', href: '/analytics#revenue', description: 'MRR & growth' },
      { name: 'DSO Analysis', href: '/analytics#dso', description: 'Days sales outstanding' },
      { name: 'Churn Risk', href: '/analytics#churn', description: 'At-risk customers' },
    ],
  },
  {
    key: 'sales',
    label: 'Sales Pipeline',
    description: 'Quotations & orders',
    icon: ShoppingCart,
    items: [
      { name: 'Pipeline Funnel', href: '/analytics#sales', description: 'Conversion rates' },
      { name: 'Quotation Trend', href: '/analytics#quotations', description: 'Monthly performance' },
    ],
  },
  {
    key: 'support',
    label: 'Support & SLA',
    description: 'Ticket performance',
    icon: Headphones,
    items: [
      { name: 'SLA Attainment', href: '/analytics#support', description: 'Response metrics' },
      { name: 'Agent Productivity', href: '/analytics#agents', description: 'Team performance' },
    ],
  },
  {
    key: 'collections',
    label: 'Collections',
    description: 'AR aging & recovery',
    icon: AlertTriangle,
    items: [
      { name: 'Invoice Aging', href: '/analytics#collections', description: 'Outstanding by age' },
      { name: 'Segment Analysis', href: '/analytics#segments', description: 'Aging by customer type' },
    ],
  },
  {
    key: 'operations',
    label: 'Operations',
    description: 'Infrastructure & expenses',
    icon: Server,
    items: [
      { name: 'Network Health', href: '/analytics#operations', description: 'Device uptime' },
      { name: 'Expense Trends', href: '/analytics#expenses', description: 'Spend analysis' },
    ],
  },
];

export default function AnalyticsLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Analytics"
      sidebarTitle="Analytics"
      sidebarDescription="Cross-module performance"
      baseRoute="/analytics"
      accentColor="cyan"
      icon={Activity}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}
