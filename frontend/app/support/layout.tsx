'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { LifeBuoy, ListChecks } from 'lucide-react';
import { cn } from '@/lib/utils';

const tabs = [
  { name: 'Tickets', href: '/support/tickets', icon: ListChecks },
  { name: 'Analytics', href: '/support/analytics', icon: LifeBuoy },
];

export default function SupportLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-teal-electric/10 border border-teal-electric/30 flex items-center justify-center">
            <LifeBuoy className="w-5 h-5 text-teal-electric" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Support</h1>
            <p className="text-slate-muted text-sm">Customer tickets, comments, and communications</p>
          </div>
        </div>
      </div>

      <div className="border-b border-slate-border overflow-x-auto">
        <nav className="-mb-px flex space-x-1 min-w-max">
          {tabs.map((tab) => {
            const isActive = tab.href === '/support/tickets' ? pathname.startsWith(tab.href) : pathname === tab.href;
            const Icon = tab.icon;
            return (
              <Link
                key={tab.name}
                href={tab.href}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                  isActive
                    ? 'border-teal-electric text-teal-electric'
                    : 'border-transparent text-slate-muted hover:text-white hover:border-slate-border'
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
