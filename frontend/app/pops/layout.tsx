'use client';

import { Radio } from 'lucide-react';
import { ModuleLayout, NavSection } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'performance',
    label: 'POP Performance',
    description: 'Network locations',
    icon: Radio,
    items: [
      { name: 'Overview', href: '/pops', description: 'Locations and KPIs' },
    ],
  },
];

export default function POPsLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="POP Performance"
      sidebarTitle="POP Performance"
      sidebarDescription="Network location analytics"
      baseRoute="/pops"
      accentColor="teal"
      icon={Radio}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}
