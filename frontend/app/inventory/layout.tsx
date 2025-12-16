"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  Package,
  Warehouse,
  ClipboardList,
  ArrowLeftRight,
  FileBarChart,
  History,
  AlertTriangle,
  Settings,
  Sun,
  Moon,
  User,
  LogOut,
  Menu,
  X,
  Boxes,
  Receipt,
  Tag,
  Hash,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@dotmac/design-tokens";
import { useAuth } from "@/lib/auth-context";
import { applyColorScheme } from "@/lib/theme";

type NavSection = {
  label: string;
  items: { href: string; label: string; icon: React.ComponentType<{ className?: string }>; desc?: string }[];
};

const navSections: NavSection[] = [
  {
    label: "Overview",
    items: [
      { href: "/inventory", label: "Dashboard", icon: LayoutDashboard, desc: "Stock overview" },
    ],
  },
  {
    label: "Stock",
    items: [
      { href: "/inventory/items", label: "Items", icon: Package, desc: "Item master with stock" },
      { href: "/inventory/warehouses", label: "Warehouses", icon: Warehouse, desc: "Storage locations" },
      { href: "/inventory/stock-ledger", label: "Stock Ledger", icon: History, desc: "Movement history" },
    ],
  },
  {
    label: "Transactions",
    items: [
      { href: "/inventory/stock-entries", label: "Stock Entries", icon: ClipboardList, desc: "In/out transactions" },
      { href: "/inventory/transfers", label: "Transfers", icon: ArrowLeftRight, desc: "Warehouse transfers" },
      { href: "/inventory/purchase-receipts", label: "Purchase Receipts", icon: Receipt, desc: "From bills" },
      { href: "/inventory/sales-issues", label: "Sales Issues", icon: Boxes, desc: "From invoices" },
    ],
  },
  {
    label: "Tracking",
    items: [
      { href: "/inventory/batches", label: "Batches", icon: Layers, desc: "Batch tracking" },
      { href: "/inventory/serials", label: "Serial Numbers", icon: Hash, desc: "Serial tracking" },
    ],
  },
  {
    label: "Reports",
    items: [
      { href: "/inventory/valuation", label: "Valuation", icon: FileBarChart, desc: "FIFO/Avg reports" },
      { href: "/inventory/summary", label: "Stock Summary", icon: Tag, desc: "Aggregated view" },
      { href: "/inventory/reorder", label: "Reorder Alerts", icon: AlertTriangle, desc: "Low stock items" },
    ],
  },
  {
    label: "Costing",
    items: [
      { href: "/inventory/landed-cost-vouchers", label: "Landed Cost", icon: Receipt, desc: "Cost allocation" },
    ],
  },
  {
    label: "Configuration",
    items: [
      { href: "/inventory/settings", label: "Settings", icon: Settings, desc: "Preferences" },
    ],
  },
];

function isActive(pathname: string, href: string) {
  if (href === "/inventory") return pathname === "/inventory";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function InventoryLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { isDarkMode, setColorScheme } = useTheme();
  const { isAuthenticated, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const toggleTheme = () => {
    const next = isDarkMode ? "light" : "dark";
    setColorScheme(next);
    applyColorScheme(next);
  };

  const renderNav = (onNavigate?: () => void) => (
    <nav className="space-y-4">
      {navSections.map((section) => (
        <div key={section.label} className="space-y-1">
          <p className="text-[11px] uppercase tracking-wider text-slate-muted px-3 mb-1">{section.label}</p>
          {section.items.map((item) => {
            const ActiveIcon = item.icon;
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => onNavigate && onNavigate()}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-amber-500/15 border border-amber-500/40 text-white"
                    : "text-slate-muted hover:text-white hover:bg-slate-elevated"
                )}
              >
                <div
                  className={cn(
                    "p-2 rounded-lg",
                    active ? "bg-amber-500/20 text-amber-300" : "bg-slate-elevated text-slate-muted"
                  )}
                >
                  <ActiveIcon className="h-4 w-4" />
                </div>
                <div className="flex flex-col">
                  <span className="font-medium">{item.label}</span>
                  {item.desc && <span className="text-[11px] text-slate-muted">{item.desc}</span>}
                </div>
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );

  return (
    <div className="space-y-4">
      {/* Mobile header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-slate-card border-b border-slate-border">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-500 to-orange-400 flex items-center justify-center shrink-0">
              <Boxes className="w-5 h-5 text-slate-deep" />
            </div>
            <div className="flex flex-col">
              <span className="font-display font-bold text-white tracking-tight">Inventory</span>
              <span className="text-[10px] text-slate-muted uppercase tracking-widest">Stock Management</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
              title={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
            >
              {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
            <button
              onClick={() => setMobileOpen((v) => !v)}
              className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
              aria-label="Toggle menu"
            >
              {mobileOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Desktop top bar */}
      <div className="hidden lg:flex items-center justify-between bg-slate-card border border-slate-border rounded-xl px-4 py-3">
        <Link href="/inventory" className="flex items-center gap-3 group">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-500 to-orange-400 flex items-center justify-center shrink-0">
            <Boxes className="w-5 h-5 text-slate-deep" />
          </div>
          <div className="flex flex-col">
            <span className="font-display font-bold text-white tracking-tight">Dotmac Inventory</span>
            <span className="text-[10px] text-slate-muted uppercase tracking-widest">Stock Management</span>
          </div>
        </Link>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleTheme}
            className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
            title={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
          >
            {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
          <div className="flex items-center gap-2">
            <div className="p-2 text-amber-300">
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
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-30 bg-black/40 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile drawer */}
      <div
        className={cn(
          "lg:hidden fixed top-[64px] bottom-0 left-0 z-40 w-72 max-w-[85vw] bg-slate-card border-r border-slate-border transform transition-transform duration-300 overflow-y-auto",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="p-4 space-y-4">
          {renderNav(() => setMobileOpen(false))}
          <div className="pt-3 border-t border-slate-border space-y-2">
            <button
              onClick={() => setColorScheme(isDarkMode ? "light" : "dark")}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 text-sm text-slate-muted transition-colors"
            >
              <span>{isDarkMode ? "Light mode" : "Dark mode"}</span>
              {isDarkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            {isAuthenticated && (
              <button
                onClick={() => { logout(); setMobileOpen(false); }}
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
        {/* Sidebar */}
        <aside className="hidden lg:block bg-slate-card border border-slate-border rounded-xl p-4 space-y-3 h-fit">
          <div className="pb-2 border-b border-slate-border">
            <h1 className="text-lg font-semibold text-white">Inventory Management</h1>
            <p className="text-slate-muted text-xs mt-1">Stock, warehouses, and movements</p>
          </div>
          {renderNav()}
        </aside>

        <main className="flex-1 space-y-6">
          {children}
        </main>
      </div>
    </div>
  );
}
