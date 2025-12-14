'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Settings,
  Mail,
  CreditCard,
  Webhook,
  MessageSquare,
  Bell,
  Palette,
  Globe,
  History,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/admin/settings', label: 'Overview', icon: Settings, exact: true },
  { href: '/admin/settings/email', label: 'Email', icon: Mail },
  { href: '/admin/settings/payments', label: 'Payments', icon: CreditCard },
  { href: '/admin/settings/webhooks', label: 'Webhooks', icon: Webhook },
  { href: '/admin/settings/sms', label: 'SMS', icon: MessageSquare },
  { href: '/admin/settings/notifications', label: 'Notifications', icon: Bell },
  { href: '/admin/settings/branding', label: 'Branding', icon: Palette },
  { href: '/admin/settings/localization', label: 'Localization', icon: Globe },
  { href: '/admin/settings/audit', label: 'Audit Log', icon: History },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex gap-6">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0">
        <nav className="space-y-1">
          {navItems.map((item) => {
            const isActive = item.exact
              ? pathname === item.href
              : pathname.startsWith(item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-teal-electric/10 text-teal-electric border border-teal-electric/30'
                    : 'text-slate-300 hover:text-white hover:bg-slate-elevated'
                )}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0">{children}</main>
    </div>
  );
}
