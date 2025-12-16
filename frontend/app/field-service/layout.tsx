'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Wrench,
  Calendar,
  Users,
  MapPin,
  BarChart3,
  Settings,
  ClipboardList,
  Truck,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/field-service', label: 'Dashboard', icon: Wrench, exact: true },
  { href: '/field-service/orders', label: 'Service Orders', icon: ClipboardList },
  { href: '/field-service/schedule', label: 'Schedule', icon: Calendar },
  { href: '/field-service/teams', label: 'Teams', icon: Users },
  { href: '/field-service/analytics', label: 'Analytics', icon: BarChart3 },
];

export default function FieldServiceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-slate-border bg-slate-card/50 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-teal-electric/20 flex items-center justify-center">
              <Truck className="w-5 h-5 text-teal-electric" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">Field Service</h1>
              <p className="text-xs text-slate-muted">Dispatch & Service Management</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/field-service/orders/new"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 transition-colors"
            >
              <ClipboardList className="w-4 h-4" />
              New Order
            </Link>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex gap-1 mt-4 -mb-4">
          {navItems.map((item) => {
            const isActive = item.exact
              ? pathname === item.href
              : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
                  isActive
                    ? 'border-teal-electric text-teal-electric'
                    : 'border-transparent text-slate-muted hover:text-white'
                )}
              >
                <item.icon className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {children}
      </div>
    </div>
  );
}
