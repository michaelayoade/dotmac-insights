'use client';

import useSWR from 'swr';
import Link from 'next/link';
import { RefreshCw, RotateCcw } from 'lucide-react';
import { webhooksApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useToast } from '@dotmac/core';
import { useState } from 'react';
import { Button } from '@/components/ui';

export default function InboundEventsPage() {
  const { toast } = useToast();
  const [provider, setProvider] = useState('');
  const { data, mutate, isLoading } = useSWR(['webhook-events', provider], () =>
    webhooksApi.getWebhookEvents({ provider: provider || undefined, limit: 100 })
  );

  const events = data?.items || [];

  const handleReplay = async (id: number) => {
    try {
      await webhooksApi.replayWebhookEvent(id);
      toast({ title: 'Replay scheduled', variant: 'success' });
      await mutate();
    } catch (err: any) {
      toast({ title: 'Replay failed', description: err?.message, variant: 'error' });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Inbound Webhook Events</h1>
          <p className="text-slate-muted">Audit inbound events and replay failures.</p>
        </div>
        <div className="flex gap-2">
          <input
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            placeholder="Filter by provider"
            className="px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-foreground text-sm focus:border-teal-electric focus:outline-none"
          />
          <Button
            onClick={() => mutate()}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-elevated text-foreground hover:bg-slate-border transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-border flex items-center justify-between">
          <p className="text-sm text-slate-muted">Events</p>
          {isLoading && <p className="text-xs text-slate-muted">Loading...</p>}
        </div>
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-slate-muted">
              <th className="px-4 py-3">ID</th>
              <th className="px-4 py-3">Provider</th>
              <th className="px-4 py-3">Event</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Received</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-border">
            {events.map((event: any) => (
              <tr key={event.id}>
                <td className="px-4 py-3 text-foreground">{event.id}</td>
                <td className="px-4 py-3 text-slate-muted">{event.provider}</td>
                <td className="px-4 py-3 text-slate-muted">{event.event_type}</td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      'px-2 py-1 rounded-full text-xs font-medium',
                      event.status === 'processed'
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-amber-500/10 text-amber-300'
                    )}
                  >
                    {event.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-muted">
                  {event.created_at ? new Date(event.created_at).toLocaleString() : '--'}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Link
                      href={`/admin/webhooks/inbound/events/${event.id}`}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-foreground text-xs hover:bg-slate-border"
                    >
                      Details
                    </Link>
                    <Button
                      onClick={() => handleReplay(event.id)}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-xs text-teal-electric hover:text-teal-glow"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Replay
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
            {!events.length && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-muted">
                  No events found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
