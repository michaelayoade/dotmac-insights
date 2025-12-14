'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useMemo, useState, useEffect } from 'react';
import { useTheme } from '@dotmac/design-tokens';
import { useAuth } from '@/lib/auth-context';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  BookOpen,
  Scale,
  FileSpreadsheet,
  TrendingUp,
  BookMarked,
  ClipboardList,
  Users,
  ArrowDownToLine,
  Landmark,
  CreditCard,
  PiggyBank,
  Lock,
  Bell,
  ShieldCheck,
  Settings,
  Receipt,
  FileText,
  Banknote,
  ChevronDown,
  ChevronRight,
  Calculator,
  Activity,
  Sun,
  Moon,
  User,
  LogOut,
  Menu,
  X,
  Building2,
  Calendar,
  FileCheck,
  Percent,
  BadgePercent,
} from 'lucide-react';

type NavSection = {
  label: string;
  items: { name: string; href: string; icon: React.ComponentType<{ className?: string }>; description?: string }[];
};

const tabGroups: NavSection[] = [
  {
    label: 'Overview',
    items: [
      { name: 'Dashboard', href: '/books', icon: LayoutDashboard, description: 'KPIs & shortcuts' },
    ],
  },
  {
    label: 'Sales',
    items: [
      { name: 'Invoices', href: '/books/ar/invoices', icon: FileSpreadsheet, description: 'Customer billing' },
      { name: 'Payments', href: '/books/ar/payments', icon: CreditCard, description: 'Incoming payments' },
      { name: 'Credit Notes', href: '/books/ar/credit-notes', icon: BookOpen, description: 'Customer credits' },
      { name: 'Customers (Finance)', href: '/books/accounts-receivable/customers', icon: Users, description: 'AR by customer' },
    ],
  },
  {
    label: 'Purchases',
    items: [
      { name: 'Bills', href: '/books/ap/bills', icon: FileSpreadsheet, description: 'Supplier invoices' },
      { name: 'Payments', href: '/books/ap/payments', icon: CreditCard, description: 'Outgoing payments' },
      { name: 'Debit Notes', href: '/books/ap/debit-notes', icon: BookOpen, description: 'Supplier credits' },
      { name: 'Suppliers (Finance)', href: '/books/accounts-payable/suppliers', icon: Users, description: 'AP by supplier' },
    ],
  },
  {
    label: 'Banking',
    items: [
      { name: 'Bank Accounts', href: '/books/bank-accounts', icon: CreditCard, description: 'Account setup' },
      { name: 'Transactions', href: '/books/bank-transactions', icon: Landmark, description: 'Activity & imports' },
    ],
  },
  {
    label: 'Payment Gateway',
    items: [
      { name: 'Online Payments', href: '/books/gateway/payments', icon: CreditCard, description: 'Card & bank payments' },
      { name: 'Bank Transfers', href: '/books/gateway/transfers', icon: Banknote, description: 'Payouts & disbursements' },
      { name: 'Banks & NUBAN', href: '/books/gateway/banks', icon: Landmark, description: 'Bank lookup' },
      { name: 'Open Banking', href: '/books/gateway/connections', icon: Building2, description: 'Linked accounts' },
    ],
  },
  {
    label: 'Tax',
    items: [
      { name: 'Tax Dashboard', href: '/books/tax', icon: BadgePercent, description: 'Tax overview' },
      { name: 'VAT', href: '/books/tax/vat', icon: Percent, description: 'Value Added Tax' },
      { name: 'WHT', href: '/books/tax/wht', icon: Receipt, description: 'Withholding Tax' },
      { name: 'PAYE', href: '/books/tax/paye', icon: Users, description: 'Employee tax' },
      { name: 'CIT', href: '/books/tax/cit', icon: Building2, description: 'Company Income Tax' },
      { name: 'Filing Calendar', href: '/books/tax/filing', icon: Calendar, description: 'Deadlines & reminders' },
      { name: 'E-Invoice', href: '/books/tax/einvoice', icon: FileCheck, description: 'FIRS BIS 3.0' },
      { name: 'Tax Settings', href: '/books/tax/settings', icon: Settings, description: 'Tax configuration' },
    ],
  },
  {
    label: 'Reports',
    items: [
      { name: 'Balance Sheet', href: '/books/balance-sheet', icon: ShieldCheck, description: 'Position overview' },
      { name: 'Income Statement', href: '/books/income-statement', icon: TrendingUp, description: 'P&L view' },
      { name: 'Cash Flow', href: '/books/cash-flow', icon: Banknote, description: 'Cash movements' },
    ],
  },
  {
    label: 'Advanced',
    items: [
      { name: 'AR Overview', href: '/books/accounts-receivable', icon: Users, description: 'Receivable health' },
      { name: 'AP Overview', href: '/books/accounts-payable', icon: ArrowDownToLine, description: 'Payables status' },
      { name: 'General Ledger', href: '/books/general-ledger', icon: BookMarked, description: 'All postings' },
      { name: 'Trial Balance', href: '/books/trial-balance', icon: Scale, description: 'Accounts snapshot' },
      { name: 'Journal Entries', href: '/books/journal-entries', icon: ClipboardList, description: 'Manual entries' },
      { name: 'Chart of Accounts', href: '/books/chart-of-accounts', icon: BookOpen, description: 'Account structure' },
      { name: 'Equity Statement', href: '/books/equity-statement', icon: PiggyBank, description: 'Equity changes' },
      { name: 'Credit Management', href: '/books/accounts-receivable/credit', icon: Lock, description: 'Limits & reviews' },
      { name: 'Dunning', href: '/books/accounts-receivable/dunning', icon: Bell, description: 'Reminders & stages' },
      { name: 'Settings', href: '/books/settings', icon: Settings, description: 'Preferences' },
    ],
  },
];

const workflowSteps = [
  { label: 'Capture transactions', badge: '1', color: 'bg-teal-500/20 text-teal-300' },
  { label: 'Manage AR/AP', badge: '2', color: 'bg-blue-500/20 text-blue-300' },
  { label: 'Reconcile banking', badge: '3', color: 'bg-emerald-500/20 text-emerald-300' },
  { label: 'Publish statements', badge: '4', color: 'bg-slate-500/20 text-slate-200' },
];

export default function BooksLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { isDarkMode, setColorScheme } = useTheme();
  const { isAuthenticated, logout } = useAuth();
  const isActiveHref = (href: string) => (href === '/books' ? pathname === '/books' : pathname.startsWith(href));

  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    const active = tabGroups.find((group) => group.items.some((item) => isActiveHref(item.href)));
    const initial: Record<string, boolean> = {};
    tabGroups.forEach((group, idx) => {
      initial[group.label] = !!active ? active.label === group.label : idx === 0;
    });
    return initial;
  });
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const activeHref = useMemo(() => {
    for (const group of tabGroups) {
      for (const item of group.items) {
        if (isActiveHref(item.href)) return item.href;
      }
    }
    return '';
  }, [pathname]);

  useEffect(() => {
    const active = tabGroups.find((group) => group.items.some((item) => isActiveHref(item.href)));
    if (!active) return;
    setOpenGroups((prev) => ({ ...prev, [active.label]: true }));
  }, [pathname]);

  const toggleGroup = (label: string) => {
    setOpenGroups((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  const quickLinks = [
    { name: 'New Invoice', href: '/books/accounts-receivable/invoices/new', icon: Receipt, tone: 'text-blue-300 bg-blue-500/10' },
    { name: 'New Bill', href: '/books/accounts-payable/bills/new', icon: FileText, tone: 'text-amber-300 bg-amber-500/10' },
    { name: 'New Payment', href: '/books/accounts-receivable/payments/new', icon: Banknote, tone: 'text-emerald-300 bg-emerald-500/10' },
    { name: 'Banking', href: '/books/bank-transactions', icon: CreditCard, tone: 'text-cyan-300 bg-cyan-500/10' },
  ];

  return (
    <div className="space-y-4">
      {/* Mobile header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-slate-card border-b border-slate-border">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-teal-electric to-teal-glow flex items-center justify-center shrink-0">
              <Activity className="w-5 h-5 text-slate-deep" />
            </div>
            <div className="flex flex-col">
              <span className="font-display font-bold text-white tracking-tight">Dotmac</span>
              <span className="text-[10px] text-slate-muted uppercase tracking-widest">Books</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
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
        <Link href="/books" className="flex items-center gap-3 group">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-teal-electric to-teal-glow flex items-center justify-center shrink-0">
            <Activity className="w-5 h-5 text-slate-deep" />
          </div>
          <div className="flex flex-col">
            <span className="font-display font-bold text-white tracking-tight">Dotmac</span>
            <span className="text-[10px] text-slate-muted uppercase tracking-widest">Books</span>
          </div>
        </Link>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setColorScheme(isDarkMode ? 'light' : 'dark')}
            className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
            title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
          <div className="flex items-center gap-2">
            <div className="p-2 text-teal-electric">
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
          <div className="space-y-2">
            {tabGroups.map((group) => {
              const open = openGroups[group.label];
              const isActiveGroup = group.items.some((item) => isActiveHref(item.href));
              return (
                <div
                  key={group.label}
                  className={cn(
                    'border rounded-lg transition-colors',
                    isActiveGroup ? 'border-teal-electric/40 bg-teal-electric/5' : 'border-slate-border'
                )}
              >
                  <button
                    onClick={() => toggleGroup(group.label)}
                    className="w-full flex items-center justify-between px-3 py-2.5 text-sm text-white hover:bg-slate-elevated/50 rounded-lg transition-colors"
                  >
                    <span className={cn(isActiveGroup ? 'text-teal-electric' : 'text-white')}>{group.label}</span>
                    {open ? (
                      <ChevronDown className="w-4 h-4 text-slate-muted" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-slate-muted" />
                    )}
                  </button>
                  {open && (
                    <div className="pb-2 px-2 space-y-1">
                      {group.items.map((item) => {
                        const isActive = activeHref === item.href;
                        const Icon = item.icon;
                        return (
                          <Link
                            key={item.href}
                            href={item.href}
                            onClick={() => setMobileMenuOpen(false)}
                            className={cn(
                              'flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors border border-transparent',
                              isActive
                                ? 'bg-teal-electric/15 text-teal-electric border-teal-electric/30 shadow-[0_0_0_1px_rgba(45,212,191,0.25)]'
                                : 'text-slate-muted hover:text-white hover:bg-slate-elevated'
                            )}
                          >
                            <Icon className="w-4 h-4" />
                            <div className="flex-1 text-left">
                              <span className="block">{item.name}</span>
                              {item.description && (
                                <span className={cn(
                                  'text-[10px] block leading-tight overflow-hidden text-ellipsis',
                                  isActive ? 'text-teal-electric/80' : 'text-slate-muted'
                                )}>
                                  {item.description}
                                </span>
                              )}
                            </div>
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
            <p className="text-xs text-slate-muted mb-2 px-1">Workspace</p>
            <div className="grid grid-cols-2 gap-2">
              {quickLinks.map((link) => {
                const Icon = link.icon;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={cn(
                      'flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center',
                      link.tone
                    )}
                  >
                    <Icon className="w-4 h-4 mb-1" />
                    <span className="text-[11px] text-slate-muted">{link.name.replace('New ', '')}</span>
                  </Link>
                );
              })}
            </div>
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
        <div className="pb-3 border-b border-slate-border flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-teal-electric to-teal-glow flex items-center justify-center shrink-0">
            <Calculator className="w-5 h-5 text-slate-deep" />
          </div>
          <div className="flex-1">
            <h1 className="text-lg font-semibold text-white">Books & Accounting</h1>
            <p className="text-slate-muted text-xs mt-1">Transactions, reconciliation, and reporting</p>
          </div>
        </div>

        <div className="space-y-2">
            {tabGroups.map((group) => {
              const open = openGroups[group.label];
              const isActiveGroup = group.items.some((item) => isActiveHref(item.href));
              return (
                <div
                key={group.label}
                className={cn(
                  'border rounded-lg transition-colors',
                  isActiveGroup ? 'border-teal-electric/40 bg-teal-electric/5' : 'border-slate-border'
                )}
              >
                <button
                  onClick={() => toggleGroup(group.label)}
                  className="w-full flex items-center justify-between px-3 py-2.5 text-sm text-white hover:bg-slate-elevated/50 rounded-lg transition-colors"
                >
                  <span className={cn(isActiveGroup ? 'text-teal-electric' : 'text-white')}>{group.label}</span>
                  {open ? (
                    <ChevronDown className="w-4 h-4 text-slate-muted" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-slate-muted" />
                  )}
                </button>
                {open && (
                  <div className="pb-2 px-2 space-y-1">
                    {group.items.map((item) => {
                      const isActive = activeHref === item.href;
                      const Icon = item.icon;
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          className={cn(
                            'flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors border border-transparent',
                            isActive
                              ? 'bg-teal-electric/15 text-teal-electric border-teal-electric/30 shadow-[0_0_0_1px_rgba(45,212,191,0.25)]'
                              : 'text-slate-muted hover:text-white hover:bg-slate-elevated'
                          )}
                        >
                          <Icon className="w-4 h-4" />
                          <div className="flex-1 text-left">
                            <span className="block">{item.name}</span>
                            {item.description && (
                            <span className={cn(
                              'text-[10px] block leading-tight overflow-hidden text-ellipsis',
                                  isActive ? 'text-teal-electric/80' : 'text-slate-muted'
                                )}>
                              {item.description}
                            </span>
                          )}
                        </div>
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
          <p className="text-xs text-slate-muted mb-2 px-1">Workspace</p>
          <div className="grid grid-cols-2 gap-2">
            {quickLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    'flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center',
                    link.tone
                  )}
                >
                  <Icon className="w-4 h-4 mb-1" />
                  <span className="text-[11px] text-slate-muted">{link.name.replace('New ', '')}</span>
                </Link>
              );
            })}
          </div>
        </div>

        {/* Books Workflow */}
        <div className="pt-3 border-t border-slate-border">
          <p className="text-xs text-slate-muted mb-2 px-1">Books Workflow</p>
          <div className="space-y-1 text-[10px] text-slate-muted px-1">
            {workflowSteps.map((step) => (
              <div key={step.label} className="flex items-center gap-2">
                <div className={cn('w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold', step.color)}>
                  {step.badge}
                </div>
                <span>{step.label}</span>
              </div>
            ))}
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="space-y-6">{children}</div>
      </div>
    </div>
  );
}
