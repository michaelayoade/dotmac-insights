'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useNotifications, useNotificationPreferences, useNotificationMutations } from '@/hooks/useApi';
import { AlertTriangle, Bell, CheckCircle2, Clock, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';

function formatDate(date?: string) {
  if (!date) return '';
  return new Date(date).toLocaleString();
}

export default function NotificationsPage() {
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const { data, error, isLoading } = useNotifications({ limit, offset });
  const { data: prefs } = useNotificationPreferences();
  const { markRead, markAllRead, updatePreferences } = useNotificationMutations();

  const list = data?.data || data?.notifications || data || [];

  const togglePref = async (eventType: string) => {
    const current = prefs?.[eventType] ?? true;
    await updatePreferences({ [eventType]: !current });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell className="w-5 h-5 text-teal-electric" />
          <h1 className="text-2xl font-bold text-white">Notifications</h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => markAllRead()}
            className="px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            Mark all read
          </button>
          <Link
            href="#prefs"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <Settings className="w-4 h-4" />
            Preferences
          </Link>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load notifications.</span>
        </div>
      )}

      <div className="space-y-2">
        {isLoading && <p className="text-slate-muted">Loading...</p>}
        {!isLoading && list.length === 0 && (
          <p className="text-slate-muted text-sm">No notifications.</p>
        )}
        {list.map((n: any) => (
          <div
            key={n.id}
            className={cn(
              'border rounded-lg p-3 flex items-center justify-between',
              n.read_at ? 'border-slate-border/60 bg-slate-card' : 'border-teal-electric/40 bg-teal-electric/5'
            )}
          >
            <div className="space-y-1">
              <p className="text-white font-semibold">{n.title || n.event_type}</p>
              {n.message && <p className="text-slate-muted text-sm">{n.message}</p>}
              <p className="text-xs text-slate-muted flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatDate(n.created_at || n.timestamp)}
              </p>
            </div>
            {!n.read_at && (
              <button
                onClick={() => markRead(n.id)}
                className="text-xs inline-flex items-center gap-1 px-2 py-1 rounded-md bg-teal-electric text-slate-950 hover:bg-teal-electric/90"
              >
                <CheckCircle2 className="w-4 h-4" /> Mark read
              </button>
            )}
          </div>
        ))}
      </div>

      <div id="prefs" className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Settings className="w-4 h-4 text-teal-electric" />
          <h2 className="text-white font-semibold text-sm">Preferences</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {Object.entries(prefs || {}).map(([eventType, enabled]) => (
            <label key={eventType} className="flex items-center gap-2 px-3 py-2 border border-slate-border rounded-lg">
              <input
                type="checkbox"
                checked={!!enabled}
                onChange={() => togglePref(eventType)}
              />
              <span className="text-slate-200 text-sm">{eventType}</span>
            </label>
          ))}
          {prefs && Object.keys(prefs).length === 0 && (
            <p className="text-slate-muted text-sm">No preference data.</p>
          )}
        </div>
      </div>
    </div>
  );
}
