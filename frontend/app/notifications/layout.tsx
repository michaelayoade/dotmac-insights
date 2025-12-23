'use client';

import { Bell } from 'lucide-react';
import { ModuleLayout } from '@/components/ModuleLayout';
import type { NavSection } from '@/components/ModuleLayout/types';

const sections: NavSection[] = [
  {
    key: 'notifications',
    label: 'Notifications',
    description: 'Alerts and preferences',
    icon: Bell,
    items: [
      { name: 'All Notifications', href: '/notifications', description: 'Inbox and settings' },
    ],
  },
];

export default function NotificationsLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Notifications"
      sidebarTitle="Notifications"
      sidebarDescription="System alerts and preferences"
      baseRoute="/notifications"
      accentColor="amber"
      icon={Bell}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}
