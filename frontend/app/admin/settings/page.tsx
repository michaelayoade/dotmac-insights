'use client';

import Link from 'next/link';
import {
  Mail,
  CreditCard,
  Webhook,
  MessageSquare,
  Bell,
  Palette,
  Globe,
  ChevronRight,
} from 'lucide-react';
import { useSettingsGroups } from '@/hooks/useApi';
import { SettingsGroupMeta } from '@/lib/api';

const groupIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  email: Mail,
  payments: CreditCard,
  webhooks: Webhook,
  sms: MessageSquare,
  notifications: Bell,
  branding: Palette,
  localization: Globe,
};

export default function SettingsPage() {
  const { data: groups, isLoading } = useSettingsGroups() as {
    data: SettingsGroupMeta[] | undefined;
    isLoading: boolean;
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-slate-muted text-sm mt-1">
          Configure application settings for email, payments, notifications, and more.
        </p>
      </header>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(7)].map((_, i) => (
            <div
              key={i}
              className="bg-slate-card border border-slate-border rounded-xl p-4 animate-pulse"
            >
              <div className="h-4 w-24 bg-slate-700 rounded mb-2" />
              <div className="h-3 w-48 bg-slate-700 rounded" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {groups?.map((group) => {
            const Icon = groupIcons[group.group] || Mail;
            return (
              <Link
                key={group.group}
                href={`/admin/settings/${group.group}`}
                className="group bg-slate-card border border-slate-border rounded-xl p-4 hover:border-teal-electric/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-teal-electric/10 flex items-center justify-center">
                      <Icon className="w-5 h-5 text-teal-electric" />
                    </div>
                    <div>
                      <h3 className="text-white font-semibold">{group.label}</h3>
                      <p className="text-slate-muted text-sm">{group.description}</p>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-slate-muted group-hover:text-teal-electric transition-colors" />
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
