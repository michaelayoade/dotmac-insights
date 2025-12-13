'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { ClipboardList, LayoutDashboard, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';

const tabs = [
  { name: 'Projects', href: '/projects', icon: ClipboardList },
  { name: 'Analytics', href: '/projects/analytics', icon: TrendingUp },
];

export default function ProjectsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Projects</h1>
          <p className="text-slate-muted text-sm">Track project delivery, financials, and tasks</p>
        </div>
      </div>

      <div className="border-b border-slate-border overflow-x-auto">
        <nav className="-mb-px flex space-x-1 min-w-max">
          {tabs.map((tab) => {
            const isActive = tab.href === '/projects' ? pathname === '/projects' : pathname.startsWith(tab.href);
            const Icon = tab.icon;
            return (
              <Link
                key={tab.name}
                href={tab.href}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                  isActive ? 'border-teal-electric text-teal-electric' : 'border-transparent text-slate-muted hover:text-white hover:border-slate-border'
                )}
              >
                <Icon className="w-4 h-4" />
                {tab.name}
              </Link>
            );
          })}
        </nav>
      </div>

      {children}
    </div>
  );
}
