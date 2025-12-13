'use client';

import Link from 'next/link';
import { Boxes, Home, Route } from 'lucide-react';

export default function InventoryHome() {
  const links = [
    { href: '/inventory/items/new', label: 'Create Item', icon: Boxes },
    { href: '/inventory/warehouses/new', label: 'Create Warehouse', icon: Home },
    { href: '/inventory/stock-entries/new', label: 'New Stock Entry', icon: Route },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Inventory</h1>
        <p className="text-slate-muted text-sm">Quick actions for items, warehouses, and stock moves.</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center gap-3 hover:border-teal-electric/50 transition"
          >
            <link.icon className="w-5 h-5 text-teal-electric" />
            <div>
              <p className="text-white font-semibold">{link.label}</p>
              <p className="text-slate-muted text-sm">Open form</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
