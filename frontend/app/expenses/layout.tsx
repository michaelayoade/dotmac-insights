"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FileText, Wallet2, Settings } from "lucide-react";
import React from "react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/expenses", label: "Overview", icon: LayoutDashboard },
  { href: "/expenses/claims", label: "Claims", icon: FileText },
  { href: "/expenses/advances", label: "Cash Advances", icon: Wallet2 },
  { href: "/expenses/settings", label: "Settings", icon: Settings },
];

function isActive(pathname: string, href: string) {
  if (href === "/expenses") return pathname === "/expenses";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function ExpensesLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="lg:flex lg:gap-8">
      <aside className="lg:w-64">
        <div className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-100 px-4 py-4">
            <p className="text-xs uppercase tracking-wide text-gray-500">Expenses</p>
            <p className="text-sm text-gray-600">Claims, advances, approvals</p>
          </div>
          <nav className="p-2">
            {navItems.map((item) => {
              const ActiveIcon = item.icon;
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition",
                    active
                      ? "bg-blue-50 text-blue-700"
                      : "text-gray-700 hover:bg-gray-50"
                  )}
                >
                  <ActiveIcon className="h-4 w-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </aside>
      <main className="mt-6 flex-1 space-y-6 lg:mt-0">
        {children}
      </main>
    </div>
  );
}
