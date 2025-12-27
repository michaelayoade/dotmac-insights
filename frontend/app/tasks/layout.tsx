'use client';

import { CheckSquare } from 'lucide-react';
import { ModuleLayout, type NavSectionType as NavSection } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'tasks',
    label: 'My Tasks',
    description: 'Unified workflow tasks',
    icon: CheckSquare,
    items: [
      { name: 'Tasks', href: '/tasks', description: 'All assigned tasks' },
    ],
  },
];

export default function TasksLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="My Tasks"
      sidebarTitle="Task Center"
      sidebarDescription="Unified workflow tasks from all modules"
      baseRoute="/tasks"
      accentColor="indigo"
      icon={CheckSquare}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}
