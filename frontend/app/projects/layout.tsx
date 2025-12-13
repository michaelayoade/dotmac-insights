'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { cn } from '@/lib/utils';
import { LayoutDashboard, ClipboardList, BarChart3, ChevronDown, ChevronRight } from 'lucide-react';

type SectionKey = 'portfolio' | 'analytics';

type NavSection = {
  key: SectionKey;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  items: { name: string; href: string; description?: string }[];
};

const sections: NavSection[] = [
  {
    key: 'portfolio',
    label: 'Portfolio',
    description: 'Projects overview & details',
    icon: LayoutDashboard,
    items: [
      { name: 'Projects', href: '/projects', description: 'All projects and status' },
    ],
  },
  {
    key: 'analytics',
    label: 'Analytics',
    description: 'Performance & progress',
    icon: BarChart3,
    items: [
      { name: 'Analytics', href: '/projects/analytics', description: 'Trends and health' },
    ],
  },
];

function isActivePath(pathname: string, href: string) {
  if (href === '/projects') return pathname === href || pathname.startsWith(`${href}/`);
  return pathname === href || pathname.startsWith(`${href}/`);
}

function getActiveSection(pathname: string): SectionKey | null {
  for (const section of sections) {
    if (section.items.some((item) => isActivePath(pathname, item.href))) return section.key;
  }
  return null;
}

export default function ProjectsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [openSections, setOpenSections] = useState<Record<SectionKey, boolean>>(() => {
    const active = getActiveSection(pathname);
    const initial: Record<SectionKey, boolean> = { portfolio: true, analytics: false };
    if (active) initial[active] = true;
    return initial;
  });

  const activeSection = useMemo(() => getActiveSection(pathname), [pathname]);
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-6">
      <aside className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4 h-fit">
        <div className="pb-3 border-b border-slate-border">
          <h1 className="text-lg font-semibold text-white">Projects</h1>
          <p className="text-slate-muted text-xs mt-1">Portfolio, delivery, and performance</p>
        </div>

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

        <div className="pt-3 border-t border-slate-border">
          <p className="text-xs text-slate-muted mb-2 px-1">Project Flow</p>
          <div className="space-y-1 text-[10px] text-slate-muted px-1">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[8px] font-bold">1</div>
              <span>Plan & scope</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center text-[8px] font-bold">2</div>
              <span>Execute & track</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-[8px] font-bold">3</div>
              <span>Deliver & review</span>
            </div>
          </div>
        </div>
      </aside>

      <div className="space-y-6">{children}</div>
    </div>
  );
}
