'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  LifeBuoy,
  ListChecks,
  BarChart3,
  ChevronDown,
  ChevronRight,
  MessageCircle,
  Inbox,
  Activity,
  AlertTriangle,
  ShieldCheck,
  Target,
  Clock,
  Users,
  Settings,
  Sun,
  Moon,
  User,
  LogOut,
  Menu,
  X,
  Headphones,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@dotmac/design-tokens';
import { useAuth } from '@/lib/auth-context';
import { useSupportDashboard, useSupportSlaBreachesSummary } from '@/hooks/useApi';

type SectionKey = 'desk' | 'insights' | 'operations' | 'content' | 'config';

type NavSection = {
  key: SectionKey;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  items: { name: string; href: string; description?: string }[];
};

const sections: NavSection[] = [
  {
    key: 'desk',
    label: 'Omnichannel Desk',
    description: 'Tickets, conversations, and assignments',
    icon: Inbox,
    items: [
      { name: 'Dashboard', href: '/support', description: 'Overview & metrics' },
      { name: 'Tickets', href: '/support/tickets', description: 'Inbox, SLA, assignments' },
      { name: 'Agents', href: '/support/agents', description: 'People, capacity, skills' },
      { name: 'Teams', href: '/support/teams', description: 'Queues, members, routing' },
    ],
  },
  {
    key: 'insights',
    label: 'Analytics',
    description: 'Performance, SLA, backlog',
    icon: BarChart3,
    items: [
      { name: 'Analytics', href: '/support/analytics', description: 'Trends, SLA attainment' },
      { name: 'CSAT', href: '/support/csat', description: 'Surveys & feedback' },
    ],
  },
  {
    key: 'operations',
    label: 'Automation & SLA',
    description: 'Rules, calendars, routing',
    icon: ShieldCheck,
    items: [
      { name: 'SLA', href: '/support/sla', description: 'Policies, calendars, breaches' },
      { name: 'Automation', href: '/support/automation', description: 'Rules & logs' },
      { name: 'Routing', href: '/support/routing', description: 'Rules, workload, health' },
    ],
  },
  {
    key: 'content',
    label: 'Knowledge & Canned',
    description: 'Knowledge base & snippets',
    icon: MessageCircle,
    items: [
      { name: 'Knowledge Base', href: '/support/kb', description: 'Categories & articles' },
      { name: 'Canned Responses', href: '/support/canned-responses', description: 'Shortcodes & templates' },
    ],
  },
  {
    key: 'config',
    label: 'Configuration',
    description: 'Support settings',
    icon: Settings,
    items: [
      { name: 'Settings', href: '/support/settings', description: 'Helpdesk configuration' },
    ],
  },
];

const workflowPhases = [
  { key: 'intake', label: 'Intake', description: 'Capture & categorize' },
  { key: 'resolve', label: 'Resolve', description: 'Assign & respond' },
  { key: 'analyze', label: 'Analyze', description: 'Improve & prevent' },
];

function isActivePath(pathname: string, href: string) {
  if (href === '/support') return pathname === '/support';
  if (href === '/support/tickets') return pathname === href || pathname.startsWith(`${href}/`);
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
  if (!sectionKey) return 'intake';
  if (sectionKey === 'desk') return 'resolve';
  return 'analyze';
}

export default function SupportLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { isDarkMode, setColorScheme } = useTheme();
  const { isAuthenticated, logout } = useAuth();
  const { data: dashboard } = useSupportDashboard();
  const { data: slaBreach } = useSupportSlaBreachesSummary({ days: 30 });

  const [openSections, setOpenSections] = useState<Record<SectionKey, boolean>>(() => {
    const activeSection = getActiveSection(pathname);
    const initial: Record<SectionKey, boolean> = {
      desk: true,
      insights: false,
      operations: false,
      content: false,
      config: false,
    };
    if (activeSection) initial[activeSection] = true;
    return initial;
  });

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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

  useEffect(() => {
    const active = getActiveSection(pathname);
    if (!active) return;
    setOpenSections((prev) => ({ ...prev, [active]: true }));
  }, [pathname]);

  const toggleSection = (key: SectionKey) => {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const overdueCount = slaBreach?.currently_overdue ?? dashboard?.metrics?.overdue_tickets ?? 0;
  const openCount = dashboard?.tickets?.open ?? 0;
  const slaAttainment = dashboard?.sla?.attainment_rate ?? 0;

  return (
    <div className="space-y-4">
      {/* Mobile header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-slate-card border-b border-slate-border">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-teal-400 to-teal-300 flex items-center justify-center shrink-0">
              <Headphones className="w-5 h-5 text-slate-deep" />
            </div>
            <div className="flex flex-col">
              <span className="font-display font-bold text-white tracking-tight">Dotmac</span>
              <span className="text-[10px] text-slate-muted uppercase tracking-widest">Support</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {overdueCount > 0 && (
              <Link href="/support/sla" className="relative p-2 text-rose-400 hover:bg-slate-elevated rounded-lg transition-colors">
                <AlertTriangle className="w-5 h-5" />
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500 text-white text-[9px] font-bold flex items-center justify-center">
                  {overdueCount > 9 ? '9+' : overdueCount}
                </span>
              </Link>
            )}
            <button
              onClick={() => setColorScheme(isDarkMode ? 'light' : 'dark')}
              className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
              title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
            <button
              onClick={() => setMobileMenuOpen((v) => !v)}
              className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Desktop top bar */}
      <div className="hidden lg:flex items-center justify-between bg-slate-card border border-slate-border rounded-xl px-4 py-3">
        <Link href="/support" className="flex items-center gap-3 group">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-teal-400 to-teal-300 flex items-center justify-center shrink-0">
            <Headphones className="w-5 h-5 text-slate-deep" />
          </div>
          <div className="flex flex-col">
            <span className="font-display font-bold text-white tracking-tight">Dotmac</span>
            <span className="text-[10px] text-slate-muted uppercase tracking-widest">Support</span>
          </div>
        </Link>
        <div className="flex items-center gap-3">
          {/* Live metrics in top bar */}
          <div className="flex items-center gap-4 px-4 py-1.5 bg-slate-elevated rounded-lg">
            <div className="flex items-center gap-1.5">
              <Inbox className="w-3.5 h-3.5 text-blue-400" />
              <span className="text-sm font-medium text-white">{openCount}</span>
              <span className="text-xs text-slate-muted">open</span>
            </div>
            <div className="w-px h-4 bg-slate-border" />
            <div className="flex items-center gap-1.5">
              <AlertTriangle className={cn('w-3.5 h-3.5', overdueCount > 0 ? 'text-rose-400' : 'text-slate-muted')} />
              <span className={cn('text-sm font-medium', overdueCount > 0 ? 'text-rose-400' : 'text-white')}>{overdueCount}</span>
              <span className="text-xs text-slate-muted">overdue</span>
            </div>
            <div className="w-px h-4 bg-slate-border" />
            <div className="flex items-center gap-1.5">
              <Target className={cn('w-3.5 h-3.5', slaAttainment >= 90 ? 'text-emerald-400' : slaAttainment >= 80 ? 'text-amber-400' : 'text-rose-400')} />
              <span className={cn('text-sm font-medium', slaAttainment >= 90 ? 'text-emerald-400' : slaAttainment >= 80 ? 'text-amber-400' : 'text-rose-400')}>
                {slaAttainment.toFixed(0)}%
              </span>
              <span className="text-xs text-slate-muted">SLA</span>
            </div>
          </div>
          <div className="w-px h-6 bg-slate-border" />
          <button
            onClick={() => setColorScheme(isDarkMode ? 'light' : 'dark')}
            className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
            title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
          <div className="flex items-center gap-2">
            <div className="p-2 text-teal-300">
              <User className="w-5 h-5" />
            </div>
            {isAuthenticated && (
              <button
                onClick={logout}
                className="p-2 text-slate-muted hover:text-coral-alert hover:bg-slate-elevated rounded-lg transition-colors"
                title="Sign out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div
          className="lg:hidden fixed inset-0 z-30 bg-black/40 backdrop-blur-sm"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Mobile drawer */}
      <div
        className={cn(
          'lg:hidden fixed top-[64px] bottom-0 left-0 z-40 w-72 max-w-[85vw] bg-slate-card border-r border-slate-border transform transition-transform duration-300 overflow-y-auto',
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="p-4 space-y-4">
          {/* Live Status */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-slate-elevated rounded-lg p-2 text-center">
              <div className="flex items-center justify-center gap-1">
                <Inbox className="w-3 h-3 text-blue-400" />
                <span className="text-lg font-bold text-white">{openCount}</span>
              </div>
              <p className="text-[10px] text-slate-muted">Open</p>
            </div>
            <div className={cn(
              'rounded-lg p-2 text-center',
              overdueCount > 0 ? 'bg-rose-500/10 border border-rose-500/30' : 'bg-slate-elevated'
            )}>
              <div className="flex items-center justify-center gap-1">
                <AlertTriangle className={cn('w-3 h-3', overdueCount > 0 ? 'text-rose-400' : 'text-slate-muted')} />
                <span className={cn('text-lg font-bold', overdueCount > 0 ? 'text-rose-400' : 'text-white')}>{overdueCount}</span>
              </div>
              <p className="text-[10px] text-slate-muted">Overdue</p>
            </div>
            <div className="bg-slate-elevated rounded-lg p-2 text-center">
              <div className="flex items-center justify-center gap-1">
                <Target className={cn('w-3 h-3', slaAttainment >= 90 ? 'text-emerald-400' : 'text-amber-400')} />
                <span className={cn('text-lg font-bold', slaAttainment >= 90 ? 'text-emerald-400' : 'text-amber-400')}>
                  {slaAttainment.toFixed(0)}%
                </span>
              </div>
              <p className="text-[10px] text-slate-muted">SLA</p>
            </div>
          </div>

          {/* Quick actions */}
          <div className="grid grid-cols-2 gap-2">
            <Link
              href="/support/tickets/new"
              onClick={() => setMobileMenuOpen(false)}
              className="flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center"
            >
              <ListChecks className="w-4 h-4 text-emerald-400 mb-1" />
              <span className="text-[11px] text-slate-muted">New Ticket</span>
            </Link>
            <Link
              href="/support/analytics"
              onClick={() => setMobileMenuOpen(false)}
              className="flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center"
            >
              <BarChart3 className="w-4 h-4 text-cyan-400 mb-1" />
              <span className="text-[11px] text-slate-muted">Analytics</span>
            </Link>
          </div>

          {/* Navigation sections */}
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
                    isActiveSection ? 'border-teal-500/40 bg-teal-500/5' : 'border-slate-border'
                  )}
                >
                  <button
                    onClick={() => toggleSection(section.key)}
                    className="w-full flex items-center justify-between px-3 py-2.5 text-sm text-white hover:bg-slate-elevated/50 rounded-lg transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <Icon className={cn('w-4 h-4', isActiveSection ? 'text-teal-400' : 'text-slate-muted')} />
                      <div className="text-left">
                        <span className={cn('block', isActiveSection && 'text-teal-300')}>{section.label}</span>
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
                            onClick={() => setMobileMenuOpen(false)}
                            className={cn(
                              'block px-3 py-2 text-sm rounded-lg transition-colors group',
                              isActive
                                ? 'bg-teal-500/20 text-teal-300'
                                : 'text-slate-muted hover:text-white hover:bg-slate-elevated/50'
                            )}
                          >
                            <span className="block">{item.name}</span>
                            {item.description && (
                              <span className={cn(
                                'text-[10px] block',
                                isActive ? 'text-teal-400/70' : 'text-slate-muted group-hover:text-slate-muted'
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

          <div className="pt-3 border-t border-slate-border space-y-2">
            <button
              onClick={() => setColorScheme(isDarkMode ? 'light' : 'dark')}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 text-sm text-slate-muted transition-colors"
            >
              <span>{isDarkMode ? 'Light mode' : 'Dark mode'}</span>
              {isDarkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            {isAuthenticated && (
              <button
                onClick={() => { logout(); setMobileMenuOpen(false); }}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-slate-elevated text-sm text-slate-muted hover:bg-slate-border/30 transition-colors"
                title="Sign out"
              >
                <span>Sign out</span>
                <LogOut className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6 pt-[64px] lg:pt-0">
        {/* Sidebar Navigation */}
        <aside className="hidden lg:block bg-slate-card border border-slate-border rounded-xl p-4 space-y-4 h-fit">
          {/* Header */}
          <div className="pb-3 border-b border-slate-border">
            <h1 className="text-lg font-semibold text-white">Support Desk</h1>
            <p className="text-slate-muted text-xs mt-1">Omnichannel helpdesk & SLA management</p>
          </div>

          {/* Live Status Indicators */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-slate-elevated rounded-lg p-2 text-center">
              <div className="flex items-center justify-center gap-1">
                <Inbox className="w-3 h-3 text-blue-400" />
                <span className="text-lg font-bold text-white">{openCount}</span>
              </div>
              <p className="text-[10px] text-slate-muted">Open</p>
            </div>
            <div className={cn(
              'rounded-lg p-2 text-center',
              overdueCount > 0 ? 'bg-rose-500/10 border border-rose-500/30' : 'bg-slate-elevated'
            )}>
              <div className="flex items-center justify-center gap-1">
                <AlertTriangle className={cn('w-3 h-3', overdueCount > 0 ? 'text-rose-400' : 'text-slate-muted')} />
                <span className={cn('text-lg font-bold', overdueCount > 0 ? 'text-rose-400' : 'text-white')}>{overdueCount}</span>
              </div>
              <p className="text-[10px] text-slate-muted">Overdue</p>
            </div>
            <div className={cn(
              'rounded-lg p-2 text-center',
              slaAttainment < 80 ? 'bg-amber-500/10 border border-amber-500/30' : 'bg-slate-elevated'
            )}>
              <div className="flex items-center justify-center gap-1">
                <Target className={cn('w-3 h-3', slaAttainment >= 90 ? 'text-emerald-400' : slaAttainment >= 80 ? 'text-amber-400' : 'text-rose-400')} />
                <span className={cn(
                  'text-lg font-bold',
                  slaAttainment >= 90 ? 'text-emerald-400' : slaAttainment >= 80 ? 'text-amber-400' : 'text-rose-400'
                )}>{slaAttainment.toFixed(0)}%</span>
              </div>
              <p className="text-[10px] text-slate-muted">SLA</p>
            </div>
          </div>

          {/* Workflow Phase */}
          <div className="bg-slate-elevated rounded-lg p-3">
            <p className="text-xs text-slate-muted mb-2">Workflow Phase</p>
            <div className="flex items-center gap-1">
              {workflowPhases.map((phase, idx) => (
                <div key={phase.key} className="flex items-center">
                  <div
                    className={cn(
                      'px-2 py-1 rounded text-xs font-medium transition-colors',
                      currentPhase === phase.key
                        ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40'
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

          {/* Navigation */}
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
                    isActiveSection ? 'border-teal-500/40 bg-teal-500/5' : 'border-slate-border'
                  )}
                >
                  <button
                    onClick={() => toggleSection(section.key)}
                    className="w-full flex items-center justify-between px-3 py-2.5 text-sm text-white hover:bg-slate-elevated/50 rounded-lg transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <Icon className={cn('w-4 h-4', isActiveSection ? 'text-teal-400' : 'text-slate-muted')} />
                      <div className="text-left">
                        <span className={cn('block', isActiveSection && 'text-teal-300')}>{section.label}</span>
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
                                ? 'bg-teal-500/20 text-teal-300'
                                : 'text-slate-muted hover:text-white hover:bg-slate-elevated/50'
                            )}
                          >
                            <span className="block">{item.name}</span>
                            {item.description && (
                              <span className={cn(
                                'text-[10px] block',
                                isActive ? 'text-teal-400/70' : 'text-slate-muted group-hover:text-slate-muted'
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
                href="/support/tickets/new"
                className="flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center"
              >
                <ListChecks className="w-4 h-4 text-emerald-400 mb-1" />
                <span className="text-xs text-slate-muted">New Ticket</span>
              </Link>
              <Link
                href="/support/tickets"
                className="flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center"
              >
                <MessageCircle className="w-4 h-4 text-amber-400 mb-1" />
                <span className="text-xs text-slate-muted">Inbox</span>
              </Link>
              <Link
                href="/support/analytics"
                className="flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center"
              >
                <BarChart3 className="w-4 h-4 text-cyan-400 mb-1" />
                <span className="text-xs text-slate-muted">Analytics</span>
              </Link>
              <Link
                href="/support/sla"
                className="flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center relative"
              >
                <AlertTriangle className="w-4 h-4 text-rose-400 mb-1" />
                <span className="text-xs text-slate-muted">SLA Watch</span>
                {overdueCount > 0 && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500 text-white text-[9px] font-bold flex items-center justify-center">
                    {overdueCount > 9 ? '9+' : overdueCount}
                  </span>
                )}
              </Link>
            </div>
          </div>

          {/* Lifecycle Guide */}
          <div className="pt-3 border-t border-slate-border">
            <p className="text-xs text-slate-muted mb-2 px-1">Omnichannel Flow</p>
            <div className="space-y-1 text-[10px] text-slate-muted px-1">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-teal-500/20 text-teal-400 flex items-center justify-center text-[8px] font-bold">1</div>
                <span>Capture (email/voice/chat)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center text-[8px] font-bold">2</div>
                <span>Triage & assign</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[8px] font-bold">3</div>
                <span>Respond & resolve</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center text-[8px] font-bold">4</div>
                <span>Analyze & improve</span>
              </div>
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <div className="space-y-6">{children}</div>
      </div>
    </div>
  );
}
