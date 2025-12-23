'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowRight,
  Star,
  Activity,
  Sun,
  Moon,
  Zap,
  TrendingUp,
  Clock,
  Building2,
  X,
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { useTheme } from '@dotmac/design-tokens';
import { applyColorScheme } from '@/lib/theme';
import { cn } from '@/lib/utils';
import { AccentColor, getCardColors } from '@/lib/config/colors';
import { MODULES, CATEGORY_META, ModuleDefinition, ModuleCategory } from '@/lib/config/modules';
import { Button } from '@/components/ui';


const DEFAULT_KEY = 'dotmac_default_module';

type ModuleWithAccess = ModuleDefinition & { hasAccess: boolean };

export default function HomePage() {
  const router = useRouter();
  const { hasAnyScope, isLoading } = useAuth();
  const { isDarkMode, setColorScheme } = useTheme();
  const [defaultModuleKey, setDefaultModuleKey] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(DEFAULT_KEY);
  });
  const hasRedirected = useRef(false);

  const toggleTheme = () => {
    const next = isDarkMode ? 'light' : 'dark';
    setColorScheme(next);
    applyColorScheme(next);
  };

  const modulesWithAccess: ModuleWithAccess[] = useMemo(
    () => MODULES.map((module) => ({
      ...module,
      hasAccess: !module.requiredScopes?.length || hasAnyScope(module.requiredScopes),
    })),
    [hasAnyScope],
  );

  const accessibleModules = modulesWithAccess;

  const defaultModule = useMemo(
    () => accessibleModules.find((m) => m.key === defaultModuleKey) || null,
    [accessibleModules, defaultModuleKey],
  );

  const handleSetDefault = (key: string) => {
    if (typeof window === 'undefined') return;
    // Toggle: if already default, unset it
    if (defaultModuleKey === key) {
      localStorage.removeItem(DEFAULT_KEY);
      setDefaultModuleKey(null);
    } else {
      localStorage.setItem(DEFAULT_KEY, key);
      setDefaultModuleKey(key);
    }
  };

  const handleResetDefault = () => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(DEFAULT_KEY);
    setDefaultModuleKey(null);
  };

  // Group modules by category
  const modulesByCategory = useMemo(() => {
    const grouped: Record<ModuleCategory, ModuleWithAccess[]> = {
      core: [],
      operations: [],
      finance: [],
      admin: [],
    };
    modulesWithAccess.forEach((mod) => {
      grouped[mod.category].push(mod);
    });
    return grouped;
  }, [modulesWithAccess]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-teal-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-deep">
      {/* Header */}
      <header className="border-b border-slate-border bg-slate-card">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-3 hover:opacity-90 transition-opacity"
            onClick={() => {
              // Skip auto-redirect when clicking the logo
              if (typeof window !== 'undefined') {
                sessionStorage.setItem('skip_home_redirect', '1');
              }
              hasRedirected.current = true;
            }}
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-400 to-cyan-400 flex items-center justify-center">
              <Zap className="w-6 h-6 text-slate-900" />
            </div>
            <div className="flex flex-col">
              <span className="font-display font-bold text-foreground tracking-tight text-lg">Dotmac</span>
              <span className="text-[10px] text-slate-muted uppercase tracking-widest">Business Operating System</span>
            </div>
          </Link>
          <Button
            onClick={toggleTheme}
            className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
            title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </Button>
        </div>
      </header>

      {/* Hero Section */}
      <div className="border-b border-slate-border bg-gradient-to-b from-slate-card to-slate-deep">
        <div className="max-w-7xl mx-auto px-6 py-12">
          <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2 text-sm font-medium text-teal-400">
                <Building2 className="w-4 h-4" />
                Enterprise Suite
              </div>
              <h1 className="text-4xl font-bold text-foreground">
                Your Business, <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-cyan-400">One Platform</span>
              </h1>
              <p className="text-slate-muted max-w-xl text-lg">
                Everything you need to run your business. HR, Sales, Support, Finance, and Operations - unified in one intelligent system.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-emerald-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">{modulesWithAccess.filter(m => !m.stub).length}</p>
                  <p className="text-xs text-slate-muted">Active Modules</p>
                </div>
              </div>
              <div className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <Clock className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">24/7</p>
                  <p className="text-xs text-slate-muted">Always Available</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-10">
        {/* Quick access tip */}
        {defaultModuleKey && defaultModule && (
          <div className={cn(
            "mb-8 flex items-center justify-between gap-3 px-4 py-3 rounded-xl",
            defaultModule.hasAccess
              ? "bg-teal-500/10 border border-teal-500/30"
              : "bg-amber-500/10 border border-amber-500/30"
          )}>
            <div className="flex items-center gap-3">
              <Star className={cn(
                "w-5 h-5 flex-shrink-0 fill-current",
                defaultModule.hasAccess ? "text-teal-400" : "text-amber-400"
              )} />
              <p className={cn("text-sm", defaultModule.hasAccess ? "text-teal-300" : "text-amber-300")}>
                <span className="font-medium">{defaultModule.name}</span>
                {defaultModule.hasAccess
                  ? " is your default workspace."
                  : " is your default but you lack access."}
              </p>
            </div>
            <Button
              onClick={handleResetDefault}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors",
                defaultModule.hasAccess
                  ? "text-teal-300 hover:text-foreground hover:bg-teal-500/20"
                  : "text-amber-300 hover:text-foreground hover:bg-amber-500/20"
              )}
              title="Reset default workspace"
            >
              <X className="w-4 h-4" />
              Reset
            </Button>
            {defaultModule.hasAccess && (
              <Link
                href={defaultModule.href}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-teal-300 hover:text-foreground hover:bg-teal-500/20 rounded-lg transition-colors"
                title="Go to default workspace"
              >
                <ArrowRight className="w-4 h-4" />
                Open default
              </Link>
            )}
          </div>
        )}

        {/* Module categories */}
        <div className="space-y-10">
          {(Object.keys(CATEGORY_META) as ModuleCategory[]).map((category) => {
            const modules = modulesByCategory[category];
            if (modules.length === 0) return null;
            const meta = CATEGORY_META[category];

            return (
              <section key={category}>
                <div className="flex items-center gap-3 mb-4">
                  <h2 className="text-lg font-semibold text-foreground">{meta.label}</h2>
                  <span className="text-sm text-slate-muted">{meta.description}</span>
                </div>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {modules.map((module) => {
                    const Icon = module.icon;
                    const isDefault = defaultModuleKey === module.key;
                    const locked = !module.hasAccess;
                    const accent = getCardColors(module.accentColor as AccentColor);

                    return (
                      <div
                        key={module.key}
                        className={cn(
                          'group rounded-2xl border bg-slate-card p-5 flex flex-col gap-4 transition-all hover:shadow-lg',
                          isDefault ? `${accent.border} ${accent.bg}` : 'border-slate-border hover:border-slate-border/80',
                          locked && 'opacity-70',
                          !module.stub && !locked && 'cursor-pointer'
                        )}
                        onClick={() => {
                          if (!module.stub && !locked) {
                            router.push(module.href);
                          }
                        }}
                      >
                        <div className="flex items-start justify-between">
                      <div className={cn('w-12 h-12 rounded-xl bg-gradient-to-br flex items-center justify-center', accent.icon, locked && 'grayscale')}>
                        <Icon className="w-6 h-6 text-slate-900" />
                      </div>
                          {isDefault && (
                            <span className={cn('text-[10px] font-semibold uppercase tracking-wide px-2 py-1 rounded-full', accent.bg, accent.text)}>
                              Default
                            </span>
                          )}
                        </div>

                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                              {module.name}
                          {locked && (
                            <span className="text-[10px] uppercase tracking-wide text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded px-2 py-0.5">
                              No access
                            </span>
                          )}
                            </h3>
                            {module.badge && (
                              <span className="text-[10px] font-medium text-slate-muted uppercase tracking-wide">
                                {module.badge}
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-slate-muted line-clamp-2">{module.description}</p>
                        </div>

                        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                          {module.stub ? (
                            <span className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-xl bg-slate-elevated text-slate-muted cursor-not-allowed flex-1 justify-center">
                              Coming Soon
                            </span>
                          ) : (
                            <>
                              <Link
                                href={module.href}
                                className="inline-flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-xl text-foreground bg-slate-elevated hover:bg-slate-border transition-colors flex-1"
                              >
                                Open
                                <ArrowRight className="w-4 h-4" />
                              </Link>
                              <Button
                                onClick={() => handleSetDefault(module.key)}
                                className={cn(
                                  'p-2 rounded-xl border transition-colors',
                                  isDefault
                                    ? `${accent.border} ${accent.bg} ${accent.text}`
                                    : 'border-slate-border text-slate-muted hover:border-slate-muted hover:text-foreground'
                                )}
                                title={isDefault ? 'Default workspace' : 'Set as default'}
                                aria-label={isDefault ? 'Default workspace' : `Set ${module.name} as default`}
                              >
                                <Star className={cn('w-4 h-4', isDefault && 'fill-current')} />
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>

        {/* Footer info */}
        <div className="mt-12 pt-8 border-t border-slate-border">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-slate-muted">
            <p>Dotmac Business Operating System - Powering modern enterprises</p>
            <div className="flex items-center gap-4">
              <Link href="/admin/settings/general" className="hover:text-foreground transition-colors">Settings</Link>
              <Link href="/admin/security" className="hover:text-foreground transition-colors">Security</Link>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
