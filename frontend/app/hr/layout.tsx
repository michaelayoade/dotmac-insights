'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useMemo, useEffect } from 'react';
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
  ChevronDown,
  ChevronRight,
  Users,
  UserPlus,
  ClipboardList,
  TrendingUp,
  Settings,
} from 'lucide-react';

// HR Information Flow:
// 1. SETUP: Define policies, structures, components (Foundation)
// 2. PEOPLE: Recruit, onboard, manage employee lifecycle (Core)
// 3. TIME & ATTENDANCE: Track time, leave, shifts (Daily Operations)
// 4. COMPENSATION: Payroll processing, salary management (Monthly Cycle)
// 5. DEVELOPMENT: Training, appraisals, career growth (Continuous)
// 6. ANALYTICS: Reports, insights, compliance (Monitoring)

type SectionKey = 'overview' | 'people' | 'time' | 'compensation' | 'development' | 'config';

type NavSection = {
  key: SectionKey;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  items: { name: string; href: string; description?: string }[];
};

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'HR overview and pending actions',
    icon: LayoutDashboard,
    items: [
      { name: 'Overview', href: '/hr', description: 'Dashboard & metrics' },
      { name: 'Analytics', href: '/hr/analytics', description: 'Reports & insights' },
    ],
  },
  {
    key: 'people',
    label: 'People Management',
    description: 'Recruitment to offboarding',
    icon: Users,
    items: [
      { name: 'Recruitment', href: '/hr/recruitment', description: 'Job openings & hiring' },
      { name: 'Lifecycle', href: '/hr/lifecycle', description: 'Onboarding & offboarding' },
    ],
  },
  {
    key: 'time',
    label: 'Time & Leave',
    description: 'Attendance and leave management',
    icon: Clock3,
    items: [
      { name: 'Attendance', href: '/hr/attendance', description: 'Check-in/out & shifts' },
      { name: 'Leave', href: '/hr/leave', description: 'Leave types & applications' },
    ],
  },
  {
    key: 'compensation',
    label: 'Compensation',
    description: 'Payroll and salary structures',
    icon: Wallet2,
    items: [
      { name: 'Payroll', href: '/hr/payroll', description: 'Salary slips & processing' },
    ],
  },
  {
    key: 'development',
    label: 'Development',
    description: 'Training and performance',
    icon: TrendingUp,
    items: [
      { name: 'Training', href: '/hr/training', description: 'Programs & events' },
      { name: 'Appraisals', href: '/hr/appraisals', description: 'Performance reviews' },
    ],
  },
  {
    key: 'config',
    label: 'Configuration',
    description: 'HR policies and settings',
    icon: Settings,
    items: [
      { name: 'Settings', href: '/hr/settings', description: 'HR configuration' },
    ],
  },
];

// Workflow phases for contextual guidance
const workflowPhases = [
  { key: 'setup', label: 'Setup', description: 'Configure HR policies' },
  { key: 'operate', label: 'Operate', description: 'Daily HR operations' },
  { key: 'analyze', label: 'Analyze', description: 'Review & improve' },
];

function isActivePath(pathname: string, href: string) {
  if (href === '/hr') return pathname === '/hr';
  return pathname === href || pathname.startsWith(`${href}/`);
}

function getActiveSection(pathname: string): SectionKey | null {
  for (const section of sections) {
    if (section.items.some((item) => isActivePath(pathname, item.href))) {
      return section.key;
    }
  }
  return null;
}

function getWorkflowPhase(sectionKey: SectionKey | null): string {
  if (!sectionKey) return 'setup';
  if (sectionKey === 'overview') return 'analyze';
  if (sectionKey === 'people' || sectionKey === 'config') return 'setup';
  return 'operate';
}

export default function HrLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const [openSections, setOpenSections] = useState<Record<SectionKey, boolean>>(() => {
    const activeSection = getActiveSection(pathname);
    const initial: Record<SectionKey, boolean> = {
      overview: true,
      people: false,
      time: false,
      compensation: false,
      development: false,
      config: false,
    };
    if (activeSection) initial[activeSection] = true;
    return initial;
  });

  // Keep the active section open on route change
  useEffect(() => {
    const activeSection = getActiveSection(pathname);
    if (!activeSection) return;
    setOpenSections((prev) => ({ ...prev, [activeSection]: true }));
  }, [pathname]);

  const activeSection = useMemo(() => getActiveSection(pathname), [pathname]);
  const currentPhase = useMemo(() => getWorkflowPhase(activeSection), [activeSection]);

  const activeHref = useMemo(() => {
    for (const section of sections) {
      for (const item of section.items) {
        if (isActivePath(pathname, item.href)) return item.href;
      }
    }
    return '';
  }, [pathname]);

  const toggleSection = (key: SectionKey) => {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
      {/* Sidebar Navigation */}
      <aside className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4 h-fit">
        {/* Header */}
        <div className="pb-3 border-b border-slate-border">
          <h1 className="text-lg font-semibold text-white">Human Resources</h1>
          <p className="text-slate-muted text-xs mt-1">People operations & workforce management</p>
        </div>

        {/* Workflow Phase Indicator */}
        <div className="bg-slate-elevated rounded-lg p-3">
          <p className="text-xs text-slate-muted mb-2">Workflow Phase</p>
          <div className="flex items-center gap-1">
            {workflowPhases.map((phase, idx) => (
              <div key={phase.key} className="flex items-center">
                <div
                  className={cn(
                    'px-2 py-1 rounded text-xs font-medium transition-colors',
                    currentPhase === phase.key
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                      : 'text-slate-muted'
                  )}
                >
                  {phase.label}
                </div>
                {idx < workflowPhases.length - 1 && (
                  <ChevronRight className="w-3 h-3 text-slate-muted mx-1" />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Navigation Sections */}
        <div className="space-y-2">
          {sections.map((section) => {
            const Icon = section.icon;
            const open = openSections[section.key];
            const isActiveSection = activeSection === section.key;

            return (
              <div
                key={section.key}
                className={cn(
                  'border rounded-lg transition-colors',
                  isActiveSection ? 'border-amber-500/40 bg-amber-500/5' : 'border-slate-border'
                )}
              >
                <button
                  onClick={() => toggleSection(section.key)}
                  className="w-full flex items-center justify-between px-3 py-2.5 text-sm text-white hover:bg-slate-elevated/50 rounded-lg transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Icon className={cn('w-4 h-4', isActiveSection ? 'text-amber-400' : 'text-slate-muted')} />
                    <div className="text-left">
                      <span className={cn('block', isActiveSection && 'text-amber-300')}>{section.label}</span>
                      <span className="text-[10px] text-slate-muted">{section.description}</span>
                    </div>
                  </div>
                  {open ? (
                    <ChevronDown className="w-4 h-4 text-slate-muted" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-slate-muted" />
                  )}
                </button>
                {open && (
                  <div className="pb-2 px-2">
                    {section.items.map((item) => {
                      const isActive = activeHref === item.href;
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          className={cn(
                            'block px-3 py-2 text-sm rounded-lg transition-colors group',
                            isActive
                              ? 'bg-amber-500/20 text-amber-300'
                              : 'text-slate-muted hover:text-white hover:bg-slate-elevated/50'
                          )}
                        >
                          <span className="block">{item.name}</span>
                          {item.description && (
                            <span className={cn(
                              'text-[10px] block',
                              isActive ? 'text-amber-400/70' : 'text-slate-muted group-hover:text-slate-muted'
                            )}>
                              {item.description}
                            </span>
                          )}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Quick Links */}
        <div className="pt-3 border-t border-slate-border">
          <p className="text-xs text-slate-muted mb-2 px-1">Quick Links</p>
          <div className="grid grid-cols-2 gap-2">
            <Link
              href="/hr/leave"
              className="flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center"
            >
              <CalendarClock className="w-4 h-4 text-amber-400 mb-1" />
              <span className="text-xs text-slate-muted">Leave</span>
            </Link>
            <Link
              href="/hr/payroll"
              className="flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center"
            >
              <Wallet2 className="w-4 h-4 text-violet-400 mb-1" />
              <span className="text-xs text-slate-muted">Payroll</span>
            </Link>
            <Link
              href="/hr/recruitment"
              className="flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center"
            >
              <UserPlus className="w-4 h-4 text-emerald-400 mb-1" />
              <span className="text-xs text-slate-muted">Recruit</span>
            </Link>
            <Link
              href="/hr/analytics"
              className="flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center"
            >
              <Activity className="w-4 h-4 text-cyan-400 mb-1" />
              <span className="text-xs text-slate-muted">Reports</span>
            </Link>
          </div>
        </div>

        {/* HR Workflow Guide */}
        <div className="pt-3 border-t border-slate-border">
          <p className="text-xs text-slate-muted mb-2 px-1">HR Workflow</p>
          <div className="space-y-1 text-[10px] text-slate-muted px-1">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-violet-500/20 text-violet-400 flex items-center justify-center text-[8px] font-bold">1</div>
              <span>Recruit & Hire</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[8px] font-bold">2</div>
              <span>Onboard Employee</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center text-[8px] font-bold">3</div>
              <span>Manage Time & Leave</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-[8px] font-bold">4</div>
              <span>Process Payroll</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center text-[8px] font-bold">5</div>
              <span>Develop & Review</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="space-y-6">{children}</div>
    </div>
  );
}
