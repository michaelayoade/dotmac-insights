'use client';

import Link from 'next/link';
import { Settings, Layers, Warehouse } from 'lucide-react';

const configCards = [
  {
    title: 'Item Groups',
    description: 'Organize items into hierarchical groups for classification',
    href: '/inventory/settings/item-groups',
    icon: Layers,
  },
  {
    title: 'Warehouses',
    description: 'Manage storage locations and warehouse hierarchy',
    href: '/inventory/warehouses',
    icon: Warehouse,
  },
];

export default function InventorySettingsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Settings className="w-5 h-5 text-teal-electric" />
        <h1 className="text-xl font-semibold text-foreground">Inventory Settings</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {configCards.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="bg-slate-card border border-slate-border rounded-xl p-6 hover:border-teal-electric/50 transition-colors group"
          >
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-lg bg-slate-elevated group-hover:bg-teal-electric/10 transition-colors">
                <card.icon className="w-6 h-6 text-teal-electric" />
              </div>
              <div>
                <h3 className="text-foreground font-medium group-hover:text-teal-electric transition-colors">
                  {card.title}
                </h3>
                <p className="text-sm text-slate-muted mt-1">{card.description}</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
