'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  CalendarClock,
  Clock3,
  Briefcase,
  Wallet2,
  GraduationCap,
  Target,
  GitMerge,
  Activity,
} from 'lucide-react';

const tabs = [
  { name: 'Overview', href: '/hr', icon: LayoutDashboard },
  { name: 'Leave', href: '/hr/leave', icon: CalendarClock },
  { name: 'Attendance', href: '/hr/attendance', icon: Clock3 },
  { name: 'Recruitment', href: '/hr/recruitment', icon: Briefcase },
  { name: 'Payroll', href: '/hr/payroll', icon: Wallet2 },
  { name: 'Training', href: '/hr/training', icon: GraduationCap },
  { name: 'Appraisals', href: '/hr/appraisals', icon: Target },
  { name: 'Lifecycle', href: '/hr/lifecycle', icon: GitMerge },
  { name: 'Analytics', href: '/hr/analytics', icon: Activity },
];

export default function HrLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Human Resources</h1>
        <p className="text-slate-muted text-sm mt-1">Leave, attendance, payroll, and people operations</p>
      </div>

      <div className="border-b border-slate-border overflow-x-auto">
        <nav className="-mb-px flex space-x-1 min-w-max">
          {tabs.map((tab) => {
            const isActive = tab.href === '/hr' ? pathname === '/hr' : pathname.startsWith(tab.href);
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
