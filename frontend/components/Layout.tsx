'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Users,
  TrendingUp,
  ChevronLeft,
  ChevronRight,
  Activity,
  Menu,
  X,
  Lightbulb,
  Lock,
  Sun,
  Moon,
  User,
  LogOut,
  Key,
  Calculator,
  ShoppingCart,
  FileText,
  CreditCard,
  Receipt,
  ArrowLeftRight,
  ArrowRightLeft,
  Boxes,
  ShieldCheck,
  Clock,
  BookOpen,
  LifeBuoy,
  ClipboardList,
  CalendarClock,
  Clock3,
  Briefcase,
  Wallet2,
  GraduationCap,
  Target,
  GitMerge,
  Bell,
  Settings,
  ChevronDown,
  Zap,
  Database,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSyncStatus } from '@/hooks/useApi';
import { useAuth, Scope } from '@/lib/auth-context';
import { useTheme } from '@dotmac/design-tokens';
import { applyColorScheme } from '@/lib/theme';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string | number;
  requiredScopes?: Scope[];
}

type BooksSection = {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  items: NavItem[];
};

const booksSections: BooksSection[] = [
  {
    label: 'Accounting',
    icon: Calculator,
    items: [
      { name: 'Dashboard', href: '/books', icon: LayoutDashboard, requiredScopes: ['analytics:read'] },
      { name: 'General Ledger', href: '/books/general-ledger', icon: Activity, requiredScopes: ['analytics:read'] },
      { name: 'Trial Balance', href: '/books/trial-balance', icon: ClipboardList, requiredScopes: ['analytics:read'] },
      { name: 'Income Statement', href: '/books/income-statement', icon: FileText, requiredScopes: ['analytics:read'] },
      { name: 'Balance Sheet', href: '/books/balance-sheet', icon: ShieldCheck, requiredScopes: ['analytics:read'] },
      { name: 'Journal Entries', href: '/books/journal-entries', icon: BookOpen, requiredScopes: ['analytics:read'] },
      { name: 'Chart of Accounts', href: '/books/chart-of-accounts', icon: FileText, requiredScopes: ['analytics:read'] },
      { name: 'Controls', href: '/books/controls', icon: Settings, requiredScopes: ['analytics:read'] },
      { name: 'Taxes', href: '/books/taxes', icon: Calculator, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Sales (AR)',
    icon: TrendingUp,
    items: [
      { name: 'AR Overview', href: '/books/accounts-receivable', icon: LayoutDashboard, requiredScopes: ['analytics:read'] },
      { name: 'Invoices', href: '/books/accounts-receivable/invoices', icon: FileText, requiredScopes: ['analytics:read'] },
      { name: 'Payments', href: '/books/accounts-receivable/payments', icon: CreditCard, requiredScopes: ['analytics:read'] },
      { name: 'Credit Notes', href: '/books/accounts-receivable/credit-notes', icon: Receipt, requiredScopes: ['analytics:read'] },
      { name: 'Credit Management', href: '/books/accounts-receivable/credit', icon: Lock, requiredScopes: ['analytics:read'] },
      { name: 'Dunning', href: '/books/accounts-receivable/dunning', icon: Bell, requiredScopes: ['analytics:read'] },
      { name: 'Customers', href: '/sales/customers', icon: Users, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Purchases (AP)',
    icon: ShoppingCart,
    items: [
      { name: 'AP Overview', href: '/books/accounts-payable', icon: LayoutDashboard, requiredScopes: ['analytics:read'] },
      { name: 'Bills', href: '/books/accounts-payable/bills', icon: Receipt, requiredScopes: ['analytics:read'] },
      { name: 'Payments', href: '/books/accounts-payable/payments', icon: ArrowRightLeft, requiredScopes: ['analytics:read'] },
      { name: 'Debit Notes', href: '/books/accounts-payable/debit-notes', icon: ArrowLeftRight, requiredScopes: ['analytics:read'] },
      { name: 'Suppliers', href: '/books/suppliers', icon: Users, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Banking',
    icon: CreditCard,
    items: [
      { name: 'Bank Accounts', href: '/books/bank-accounts', icon: Wallet2, requiredScopes: ['analytics:read'] },
      { name: 'Transactions & Uploads', href: '/books/bank-transactions', icon: CreditCard, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Inventory & Assets',
    icon: Boxes,
    items: [
      { name: 'Inventory', href: '/inventory', icon: Boxes, requiredScopes: ['analytics:read'] },
      { name: 'Items', href: '/inventory/items', icon: ClipboardList, requiredScopes: ['analytics:read'] },
      { name: 'Stock Entries', href: '/inventory/stock-entries', icon: ArrowRightLeft, requiredScopes: ['analytics:read'] },
      { name: 'Warehouses', href: '/inventory/warehouses', icon: LayoutDashboard, requiredScopes: ['analytics:read'] },
      { name: 'Valuation', href: '/inventory/valuation', icon: Activity, requiredScopes: ['analytics:read'] },
      { name: 'Landed Cost', href: '/inventory/landed-cost-vouchers', icon: ShoppingCart, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Reports',
    icon: TrendingUp,
    items: [
      { name: 'Reports Home', href: '/reports', icon: TrendingUp, requiredScopes: ['analytics:read'] },
      { name: 'Books Docs & Exports', href: '/books/docs', icon: BookOpen, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Docs & Help',
    icon: BookOpen,
    items: [
      { name: 'Documentation', href: '/books/docs', icon: BookOpen, requiredScopes: ['analytics:read'] },
      { name: 'How to Use', href: '/books/docs#help', icon: LifeBuoy, requiredScopes: ['analytics:read'] },
    ],
  },
];

const navigationGroups: { label: string; items: NavItem[] }[] = [
  {
    label: 'Sales (AR)',
    items: [
      { name: 'Dashboard', href: '/sales', icon: LayoutDashboard, requiredScopes: ['analytics:read'] },
      { name: 'Invoices', href: '/sales/invoices', icon: FileText, requiredScopes: ['analytics:read'] },
      { name: 'Payments', href: '/sales/payments', icon: CreditCard, requiredScopes: ['analytics:read'] },
      { name: 'Credit Notes', href: '/sales/credit-notes', icon: Receipt, requiredScopes: ['analytics:read'] },
      { name: 'Orders', href: '/sales/orders', icon: ShoppingCart, requiredScopes: ['analytics:read'] },
      { name: 'Quotations', href: '/sales/quotations', icon: FileText, requiredScopes: ['analytics:read'] },
      { name: 'Customers', href: '/sales/customers', icon: Users, requiredScopes: ['analytics:read'] },
      { name: 'Analytics', href: '/sales/analytics', icon: TrendingUp, requiredScopes: ['analytics:read'] },
      { name: 'Insights', href: '/sales/insights', icon: Lightbulb, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'HR',
    items: [
      { name: 'Overview', href: '/hr', icon: LayoutDashboard, requiredScopes: ['hr:read'] },
      { name: 'Leave', href: '/hr/leave', icon: CalendarClock, requiredScopes: ['hr:read'] },
      { name: 'Attendance', href: '/hr/attendance', icon: Clock3, requiredScopes: ['hr:read'] },
      { name: 'Recruitment', href: '/hr/recruitment', icon: Briefcase, requiredScopes: ['hr:read'] },
      { name: 'Payroll', href: '/hr/payroll', icon: Wallet2, requiredScopes: ['hr:read'] },
      { name: 'Training', href: '/hr/training', icon: GraduationCap, requiredScopes: ['hr:read'] },
      { name: 'Appraisals', href: '/hr/appraisals', icon: Target, requiredScopes: ['hr:read'] },
      { name: 'Lifecycle', href: '/hr/lifecycle', icon: GitMerge, requiredScopes: ['hr:read'] },
      { name: 'Analytics', href: '/hr/analytics', icon: Activity, requiredScopes: ['hr:read'] },
    ],
  },
  {
    label: 'Purchasing (AP)',
    items: [
      { name: 'Dashboard', href: '/purchasing', icon: ShoppingCart, requiredScopes: ['analytics:read'] },
      { name: 'Bills', href: '/purchasing/bills', icon: Receipt, requiredScopes: ['analytics:read'] },
      { name: 'Payments', href: '/purchasing/payments', icon: CreditCard, requiredScopes: ['analytics:read'] },
      { name: 'Orders', href: '/purchasing/orders', icon: ShoppingCart, requiredScopes: ['analytics:read'] },
      { name: 'Debit Notes', href: '/purchasing/debit-notes', icon: ArrowLeftRight, requiredScopes: ['analytics:read'] },
      { name: 'Aging', href: '/purchasing/aging', icon: Clock, requiredScopes: ['analytics:read'] },
      { name: 'Analytics', href: '/purchasing/analytics', icon: TrendingUp, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Books',
    items: [
      { name: 'Dashboard', href: '/books', icon: LayoutDashboard, requiredScopes: ['analytics:read'] },
      { name: 'General (GL/Statements)', href: '/books/general-ledger', icon: Activity, requiredScopes: ['analytics:read'] },
      { name: 'Accounts Receivable', href: '/books/accounts-receivable', icon: Users, requiredScopes: ['analytics:read'] },
      { name: 'AR Credit', href: '/books/accounts-receivable/credit', icon: Lock, requiredScopes: ['analytics:read'] },
      { name: 'Dunning', href: '/books/accounts-receivable/dunning', icon: Bell, requiredScopes: ['analytics:read'] },
      { name: 'Accounts Payable', href: '/books/accounts-payable', icon: ArrowLeftRight, requiredScopes: ['analytics:read'] },
      { name: 'Banking', href: '/books/bank-transactions', icon: CreditCard, requiredScopes: ['analytics:read'] },
      { name: 'Taxes', href: '/books/taxes', icon: FileText, requiredScopes: ['analytics:read'] },
      { name: 'Controls', href: '/books/controls', icon: ClipboardList, requiredScopes: ['analytics:read'] },
      { name: 'Docs', href: '/books/docs', icon: BookOpen, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Inventory',
    items: [
      { name: 'Valuation', href: '/inventory/valuation', icon: Activity, requiredScopes: ['analytics:read'] },
      { name: 'Landed Cost', href: '/inventory/landed-cost-vouchers', icon: ShoppingCart, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Reports',
    items: [
      { name: 'Overview', href: '/reports', icon: TrendingUp, requiredScopes: ['analytics:read'] },
      { name: 'Revenue', href: '/reports/revenue', icon: FileText, requiredScopes: ['analytics:read'] },
      { name: 'Expenses', href: '/reports/expenses', icon: FileText, requiredScopes: ['analytics:read'] },
      { name: 'Profitability', href: '/reports/profitability', icon: Calculator, requiredScopes: ['analytics:read'] },
      { name: 'Cash Position', href: '/reports/cash-position', icon: CreditCard, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Support',
    items: [
      { name: 'Tickets', href: '/support/tickets', icon: LifeBuoy, requiredScopes: ['analytics:read'] },
      { name: 'Analytics', href: '/support/analytics', icon: Activity, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Notifications',
    items: [
      { name: 'Inbox', href: '/notifications', icon: Bell, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Projects',
    items: [
      { name: 'Projects', href: '/projects', icon: ClipboardList, requiredScopes: ['explore:read'] },
    ],
  },
  {
    label: 'Customers',
    items: [
      { name: 'Customer 360', href: '/customers', icon: Users, requiredScopes: ['customers:read', 'explore:read'] },
      { name: 'Analytics', href: '/customers/analytics', icon: TrendingUp, requiredScopes: ['analytics:read'] },
      { name: 'Insights', href: '/customers/insights', icon: Lightbulb, requiredScopes: ['analytics:read'] },
    ],
  },
  {
    label: 'Data',
    items: [
      { name: 'Data Explorer', href: '/explorer', icon: Database, requiredScopes: ['explore:read'] },
    ],
  },
];

// Keys in sync status response that represent actual sync sources (have .status property)
const SYNC_SOURCE_KEYS = ['splynx', 'erpnext', 'chatwoot'] as const;

function ThemeToggle({ collapsed }: { collapsed?: boolean }) {
  const { isDarkMode, setColorScheme } = useTheme();
  const toggle = () => {
    const next = isDarkMode ? 'light' : 'dark';
    setColorScheme(next);
    applyColorScheme(next);
  };

  return (
    <button
      onClick={toggle}
      className={cn(
        'flex items-center justify-center rounded-lg text-slate-muted hover:text-foreground hover:bg-slate-elevated transition-colors',
        collapsed ? 'w-10 h-10' : 'w-full px-3 py-2 gap-2'
      )}
      title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDarkMode ? (
        <>
          <Sun className="w-5 h-5" />
          {!collapsed && <span className="text-sm">Light Mode</span>}
        </>
      ) : (
        <>
          <Moon className="w-5 h-5" />
          {!collapsed && <span className="text-sm">Dark Mode</span>}
        </>
      )}
    </button>
  );
}

function SyncStatusIndicator() {
  const { isAuthenticated } = useAuth();
  const { data: status, error } = useSyncStatus({
    isPaused: () => !isAuthenticated,
  });

  if (error) {
    return (
      <div className="flex items-center gap-2 text-coral-alert text-xs">
        <span className="w-2 h-2 rounded-full bg-coral-alert" />
        <span>Disconnected</span>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="flex items-center gap-2 text-slate-muted text-xs">
        <span className="w-2 h-2 rounded-full bg-slate-muted animate-pulse" />
        <span>Checking...</span>
      </div>
    );
  }

  // Filter to only sync source entries (exclude celery_enabled, celery_workers, etc.)
  const syncSources = SYNC_SOURCE_KEYS
    .filter((key) => status[key] && typeof status[key] === 'object' && 'status' in status[key])
    .map((key) => status[key]);

  const allSynced = syncSources.length === 0 || syncSources.every(
    (s) => s && (s.status === 'completed' || s.status === 'never_synced')
  );

  return (
    <div className={cn(
      'flex items-center gap-2 text-xs',
      allSynced ? 'text-teal-electric' : 'text-amber-warn'
    )}>
      <span className={cn(
        'w-2 h-2 rounded-full',
        allSynced ? 'bg-teal-electric' : 'bg-amber-warn animate-pulse'
      )} />
      <span>{allSynced ? 'Synced' : 'Syncing...'}</span>
    </div>
  );
}

function AuthStatusIndicator({ collapsed }: { collapsed?: boolean }) {
  const { isAuthenticated, isLoading, scopes, login, logout } = useAuth();
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [tokenValue, setTokenValue] = useState('');

  const handleSetToken = () => {
    if (tokenValue.trim()) {
      login(tokenValue.trim());
      setTokenValue('');
      setShowTokenInput(false);
    }
  };

  if (isLoading) {
    return (
      <div className={cn(
        'flex items-center text-slate-muted text-xs',
        collapsed ? 'justify-center' : 'gap-2 px-3'
      )}>
        <span className="w-2 h-2 rounded-full bg-slate-muted animate-pulse" />
        {!collapsed && <span>Checking auth...</span>}
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className={cn('text-xs', collapsed && 'flex justify-center')}>
        {showTokenInput ? (
          <div className="px-3 space-y-2">
            <input
              type="password"
              value={tokenValue}
              onChange={(e) => setTokenValue(e.target.value)}
              placeholder="Paste JWT token..."
              className="w-full px-2 py-1.5 bg-slate-elevated border border-slate-border rounded text-foreground text-xs placeholder:text-slate-muted focus:outline-none focus:border-teal-electric"
              onKeyDown={(e) => e.key === 'Enter' && handleSetToken()}
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={handleSetToken}
                className="flex-1 px-2 py-1 bg-teal-electric text-slate-deep rounded text-xs font-medium hover:bg-teal-glow transition-colors"
              >
                Set Token
              </button>
              <button
                onClick={() => { setShowTokenInput(false); setTokenValue(''); }}
                className="px-2 py-1 text-slate-muted hover:text-foreground transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowTokenInput(true)}
            className={cn(
              'flex items-center rounded-lg text-amber-warn hover:text-amber-warn/80 hover:bg-slate-elevated transition-colors',
              collapsed ? 'justify-center p-2' : 'gap-2 px-3 py-2 w-full'
            )}
            title="Set authentication token"
            data-auth-token-cta
          >
            <Key className="w-4 h-4" />
            {!collapsed && <span>Set Token</span>}
          </button>
        )}
      </div>
    );
  }

  // Authenticated state
  const scopeCount = scopes.length;
  const isDevMode = process.env.NODE_ENV === 'development';

  return (
    <div className={cn('text-xs', collapsed && 'flex flex-col items-center gap-2')}>
      {/* User status */}
      <div className={cn(
        'flex items-center text-teal-electric',
        collapsed ? 'justify-center' : 'gap-2 px-3'
      )}>
        <User className="w-4 h-4" />
        {!collapsed && (
          <span>
            {isDevMode ? 'Dev Token' : 'Authenticated'}
            {scopeCount > 0 && <span className="text-slate-muted ml-1">({scopeCount} scopes)</span>}
          </span>
        )}
      </div>

      {/* Logout button */}
      {!isDevMode && (
        <button
          onClick={logout}
          className={cn(
            'flex items-center rounded-lg text-slate-muted hover:text-coral-alert hover:bg-slate-elevated transition-colors mt-1',
            collapsed ? 'justify-center p-2' : 'gap-2 px-3 py-1.5 w-full'
          )}
          title="Sign out"
        >
          <LogOut className="w-4 h-4" />
          {!collapsed && <span>Sign Out</span>}
        </button>
      )}
    </div>
  );
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const { hasAnyScope, isAuthenticated } = useAuth();
  const { isDarkMode } = useTheme();
  const rootSegment = pathname.split('/')[1] || '';
  const isBooksShell =
    rootSegment === 'books' ||
    rootSegment === 'inventory' ||
    rootSegment === 'reports' ||
    (rootSegment === 'sales' && pathname.startsWith('/sales/customers'));
  const isHrShell = rootSegment === 'hr';
  const sidebarBg = isDarkMode ? 'bg-slate-950 border-slate-900' : 'bg-white border-slate-200';
  const sectionCard = isDarkMode ? 'bg-slate-900/70 border-slate-800' : 'bg-white border-slate-200';
  const sectionHover = isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-slate-100';

  // Filter navigation groups based on user scopes
  type NavNode = NavItem & { accessibleSelf: boolean; visible: boolean };
  const filteredGroups = useMemo(() => {
    const baseGroups = isBooksShell
      ? navigationGroups.filter((group) => group.label === 'Books')
      : isHrShell
        ? navigationGroups.filter((group) => group.label === 'HR')
        : navigationGroups;

    return baseGroups.map((group) => {
      const items: NavNode[] = group.items.map((item) => {
        const accessibleSelf = !item.requiredScopes || item.requiredScopes.length === 0
          ? true
          : (isAuthenticated && hasAnyScope(item.requiredScopes));
        const visible = accessibleSelf;
        return { ...item, accessibleSelf, visible };
      }).filter((item) => item.visible);
      return { label: group.label, items };
    }).filter((group) => group.items.length > 0);
  }, [isAuthenticated, hasAnyScope, isBooksShell, isHrShell]);

  const filteredBooksSections = useMemo(() => {
    return booksSections.map((section) => {
      const items = section.items
        .map((item) => {
          const accessibleSelf = !item.requiredScopes || item.requiredScopes.length === 0
            ? true
            : (isAuthenticated && hasAnyScope(item.requiredScopes));
          const visible = accessibleSelf;
          return { ...item, accessibleSelf, visible };
        })
        .filter((item) => item.visible);
      return { ...section, items };
    }).filter((section) => section.items.length > 0);
  }, [hasAnyScope, isAuthenticated]);

  const [openSections, setOpenSections] = useState<string[]>([]);

  // Load saved preference after hydration (avoids SSR mismatch)
  useEffect(() => {
    const saved = localStorage.getItem('sidebar_collapsed');
    if (saved) setCollapsed(JSON.parse(saved));
    setHydrated(true);
  }, []);

  // Persist collapsed state only after initial hydration
  useEffect(() => {
    if (hydrated) {
      localStorage.setItem('sidebar_collapsed', JSON.stringify(collapsed));
    }
  }, [collapsed, hydrated]);

  const isNodeActive = useCallback((href: string): boolean => {
    if (pathname === href) return true;
    return pathname.startsWith(`${href}/`);
  }, [pathname]);

  useEffect(() => {
    if (!isBooksShell) return;
    const activeLabels = filteredBooksSections
      .filter((section) => section.items.some((item) => isNodeActive(item.href)))
      .map((section) => section.label);
    setOpenSections((prev) => {
      if (prev.length > 0) {
        const merged = new Set([...prev, ...activeLabels]);
        return Array.from(merged);
      }
      return activeLabels.length ? activeLabels : filteredBooksSections.map((s) => s.label);
    });
  }, [filteredBooksSections, isBooksShell, pathname, isNodeActive]);

  const renderDesktopNode = (node: NavNode): React.ReactNode => {
    if (!node.visible) return null;

    const active = isNodeActive(node.href);
    const isDisabled = !node.accessibleSelf;

    const content = (
      <div
        className={cn(
          'group flex items-center rounded-lg transition-all duration-200 relative',
          collapsed ? 'justify-center p-3' : 'gap-3 px-3 py-2.5',
          active
            ? 'bg-teal-electric/10 text-teal-electric'
            : 'text-slate-muted hover:text-foreground hover:bg-slate-elevated',
          isDisabled && 'cursor-not-allowed text-slate-muted/50 hover:bg-transparent hover:text-slate-muted/50'
        )}
      >
        <node.icon className={cn('w-5 h-5 shrink-0', active && 'drop-shadow-[0_0_8px_rgba(0,212,170,0.5)]')} />
        {!collapsed && <span className="font-medium flex-1 truncate">{node.name}</span>}
        {isDisabled && !collapsed && <Lock className="w-4 h-4" />}
        {active && !isDisabled && (
          <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-teal-electric rounded-r-full" />
        )}

        {/* Tooltip for collapsed state */}
        {collapsed && (
          <div className="absolute left-full ml-2 px-2 py-1 bg-slate-elevated border border-slate-border rounded text-sm text-foreground opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50 flex items-center gap-2">
            {isDisabled && <Lock className="w-3 h-3" />}
            {node.name}
          </div>
        )}
      </div>
    );

    const wrapper = isDisabled ? (
      <div title="You don't have permission to access this section">
        {content}
      </div>
    ) : (
      <Link href={node.href}>
        {content}
      </Link>
    );

    return <div key={node.href}>{wrapper}</div>;
  };

  const renderBooksDesktopNav = () => (
    <nav className="flex-1 p-3 space-y-2 overflow-y-auto">
      {filteredBooksSections.map((section) => {
        const isOpen = openSections.includes(section.label);
        return (
          <div key={section.label} className={cn('rounded-lg border', sectionCard)}>
            <button
              onClick={() => setOpenSections((prev) =>
                prev.includes(section.label)
                  ? prev.filter((l) => l !== section.label)
                  : [...prev, section.label]
              )}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-foreground transition-colors',
                sectionHover,
                collapsed && 'justify-center'
              )}
            >
              <section.icon className="w-5 h-5 shrink-0" />
              {!collapsed && <span className="flex-1 text-left">{section.label}</span>}
              {!collapsed && (
                isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />
              )}
            </button>
            <div
              className={cn(
                'overflow-hidden transition-[max-height] duration-200',
                isOpen ? 'max-h-[1200px]' : 'max-h-0'
              )}
            >
              <div className="space-y-1 px-1 pb-2">
                {section.items.map((item) => (
                  <div key={item.href} className="pl-2">
                    {renderDesktopNode(item as NavNode)}
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      })}
    </nav>
  );

  const renderBooksMobileNav = () => (
    <nav className="p-4 space-y-3">
      {filteredBooksSections.map((section) => {
        const isOpen = openSections.includes(section.label);
        return (
          <div key={section.label} className={cn('rounded-lg border', sectionCard)}>
            <button
              onClick={() => setOpenSections((prev) =>
                prev.includes(section.label)
                  ? prev.filter((l) => l !== section.label)
                  : [...prev, section.label]
              )}
              className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-foreground"
            >
              <section.icon className="w-5 h-5" />
              <span className="flex-1 text-left">{section.label}</span>
              {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>
            {isOpen && (
              <div className="space-y-1 px-2 pb-2">
                {section.items.map((item) => {
                  const active = isNodeActive(item.href);
                  const isDisabled = !(item as NavNode).accessibleSelf;
                  const content = (
                    <div
                      className={cn(
                        'flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200',
                        active
                          ? 'bg-teal-electric/10 text-teal-electric'
                          : 'text-slate-muted hover:text-foreground hover:bg-slate-elevated',
                        isDisabled && 'cursor-not-allowed text-slate-muted/50 hover:bg-transparent hover:text-slate-muted/50'
                      )}
                    >
                      <item.icon className="w-5 h-5" />
                      <span className="font-medium flex-1">{item.name}</span>
                      {isDisabled && <Lock className="w-4 h-4" />}
                    </div>
                  );

                  return isDisabled ? (
                    <div key={item.href} title="You don't have permission to access this section">
                      {content}
                    </div>
                  ) : (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      {content}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </nav>
  );

  return (
    <div className="min-h-screen bg-slate-deep">
      {/* Mobile header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-slate-card border-b border-slate-border">
        <div className="flex items-center justify-between px-4 py-3">
          <Link
            href="/"
            className="flex items-center gap-3 hover:opacity-90 transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-teal-400 to-cyan-400 flex items-center justify-center">
              <Zap className="w-5 h-5 text-slate-deep" />
            </div>
            <span className="font-display font-bold text-foreground">Dotmac</span>
          </Link>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 text-slate-muted hover:text-foreground transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-electric"
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-sidebar"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" aria-hidden="true" /> : <Menu className="w-6 h-6" aria-hidden="true" />}
          </button>
        </div>
      </div>

      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <nav
        id="mobile-sidebar"
        role="navigation"
        aria-label="Mobile navigation"
        className={cn(
          'lg:hidden fixed top-14 left-0 bottom-0 z-40 w-64 border-r transform transition-transform duration-300',
          sidebarBg,
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {isBooksShell ? renderBooksMobileNav() : (
          <nav className="p-4 space-y-4">
            {filteredGroups.map((group) => (
              <div key={group.label} className="space-y-2">
                <p className="text-[11px] uppercase tracking-[0.12em] text-slate-muted px-2">{group.label}</p>
                <div className="space-y-1">
                  {group.items.map((item) => {
                    const active = isNodeActive(item.href);
                    const isDisabled = !item.accessibleSelf;
                    const content = (
                      <div
                        className={cn(
                          'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
                          active
                            ? 'bg-teal-electric/10 text-teal-electric'
                            : 'text-slate-muted hover:text-foreground hover:bg-slate-elevated',
                          isDisabled && 'cursor-not-allowed text-slate-muted/50 hover:bg-transparent hover:text-slate-muted/50'
                        )}
                      >
                        <item.icon className="w-5 h-5" />
                        <span className="font-medium flex-1">{item.name}</span>
                        {isDisabled && <Lock className="w-4 h-4" />}
                      </div>
                    );

                    return isDisabled ? (
                      <div key={item.href} title="You don't have permission to access this section">
                        {content}
                      </div>
                    ) : (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => setMobileMenuOpen(false)}
                      >
                        {content}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
        )}
        {/* Mobile bottom controls */}
        <div className="absolute bottom-4 left-4 right-4 space-y-3">
          <AuthStatusIndicator collapsed={false} />
          <ThemeToggle collapsed={false} />
        </div>
      </nav>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          'hidden lg:flex fixed left-0 top-0 bottom-0 z-40 flex-col border-r transition-all duration-300',
          sidebarBg,
          collapsed ? 'w-16' : 'w-64'
        )}
      >
        {/* Logo */}
        <Link
          href="/"
          className={cn(
            'flex items-center h-16 border-b border-slate-border px-4 hover:opacity-90 transition-opacity',
            collapsed ? 'justify-center' : 'gap-3'
          )}
          title="Back to Home"
        >
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-teal-400 to-cyan-400 flex items-center justify-center shrink-0 glow-teal">
            <Zap className="w-5 h-5 text-slate-deep" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-display font-bold text-foreground tracking-tight">Dotmac</span>
              <span className="text-[10px] text-slate-muted uppercase tracking-widest">BOS</span>
            </div>
          )}
        </Link>

        {/* Navigation */}
        {isBooksShell ? renderBooksDesktopNav() : (
          <nav className="flex-1 p-3 space-y-4 overflow-y-auto">
            {filteredGroups.map((group) => (
              <div key={group.label} className="space-y-2">
                {!collapsed && (
                  <p className="text-[11px] uppercase tracking-[0.12em] text-slate-muted px-2">
                    {group.label}
                  </p>
                )}
                <div className="space-y-1">
                  {group.items.map((item) => (
                    <div key={item.href}>{renderDesktopNode(item)}</div>
                  ))}
                </div>
              </div>
            ))}
          </nav>
        )}

        {/* Bottom section */}
        <div className={cn(
          'border-t border-slate-border p-3',
          collapsed && 'flex flex-col items-center'
        )}>
          {/* Auth status */}
          <div className="mb-3">
            <AuthStatusIndicator collapsed={collapsed} />
          </div>

          {/* Sync status */}
          {!collapsed && (
            <div className="mb-3 px-3">
              <SyncStatusIndicator />
            </div>
          )}

          {/* Theme toggle */}
          <div className="mb-2">
            <ThemeToggle collapsed={collapsed} />
          </div>

          {/* Collapse button */}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={cn(
              'flex items-center justify-center rounded-lg text-slate-muted hover:text-foreground hover:bg-slate-elevated transition-colors',
              collapsed ? 'w-10 h-10' : 'w-full px-3 py-2 gap-2'
            )}
          >
            {collapsed ? (
              <ChevronRight className="w-5 h-5" />
            ) : (
              <>
                <ChevronLeft className="w-5 h-5" />
                <span className="text-sm">Collapse</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main
        className={cn(
          'min-h-screen transition-all duration-300 pt-14 lg:pt-0',
          collapsed ? 'lg:ml-16' : 'lg:ml-64'
        )}
      >
        <div className="p-4 lg:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
