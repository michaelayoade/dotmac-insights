'use client';

import Link from 'next/link';
import { Settings, Users, Building2, Award } from 'lucide-react';

const configCards = [
  {
    title: 'Employees',
    description: 'Manage employee records, personal info, and employment details',
    href: '/hr/masters/employees',
    icon: Users,
  },
  {
    title: 'Departments',
    description: 'Define organizational structure and departments',
    href: '/hr/masters/departments',
    icon: Building2,
  },
  {
    title: 'Designations',
    description: 'Manage job titles and roles within the organization',
    href: '/hr/masters/designations',
    icon: Award,
  },
];

export default function HRMastersPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Settings className="w-5 h-5 text-teal-electric" />
        <h1 className="text-xl font-semibold text-white">HR Masters</h1>
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
                <h3 className="text-white font-medium group-hover:text-teal-electric transition-colors">
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
