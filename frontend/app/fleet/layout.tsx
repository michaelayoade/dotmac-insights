'use client';

import { Car, LayoutDashboard } from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout, QuickLink } from '@/components/ModuleLayout';
import type { NavSection } from '@/components/ModuleLayout/types';

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Fleet Overview',
    description: 'Vehicle coverage and compliance',
    icon: LayoutDashboard,
    items: [
      { name: 'Dashboard', href: '/fleet', description: 'Vehicles, insurance, and status' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'Vehicles', href: '/fleet', icon: Car, color: 'orange-400' },
];

export default function FleetLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('fleet:read');

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-400" />
      </div>
    );
  }

  if (!hasAccess) {
    return (
      <div className="min-h-screen bg-slate-deep p-8">
        <AccessDenied />
      </div>
    );
  }

  return (
    <ModuleLayout
      moduleName="Dotmac Fleet"
      moduleSubtitle="Operations"
      sidebarTitle="Fleet Operations"
      sidebarDescription="Vehicles, insurance & driver assignments"
      baseRoute="/fleet"
      accentColor="orange"
      icon={Car}
      sections={sections}
      quickLinks={quickLinks}
    >
      {children}
    </ModuleLayout>
  );
}
