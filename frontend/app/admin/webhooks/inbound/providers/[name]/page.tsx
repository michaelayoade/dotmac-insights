'use client';

import useSWR from 'swr';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { RefreshCw, ArrowLeft, Activity, RotateCcw } from 'lucide-react';
import { webhooksApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useToast } from '@dotmac/core';

export default function ProviderDetailPage() {
  const params = useParams();
  const provider = params.name as string;
  const { toast } = useToast();

  const { data: stats, mutate } = useSWR(provider ? ['webhook-provider', provider] : null, () =>
    webhooksApi.getWebhookProviderStats(provider)
  );
  const { data: events, mutate: mutateEvents } = useSWR(provider ? ['webhook-events', provider] : null, () =>
    webhooksApi.getWebhookEvents({ provider, limit: 50 })
  );

  const handleReplay = async (id: number) => {
    try {
      await webhooksApi.replayWebhookEvent(id);
      toast({ title: 'Replay scheduled', variant: 'success' });
      await mutateEvents();
    } catch (err: any) {
      toast({ title: 'Failed to replay event', description: err?.message, variant: 'error' });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/admin/webhooks/inbound" className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-white hover:bg-slate-border">
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>
          <h1 className="text-2xl font-bold text-white capitalize">{provider}</h1>
        </div>
        <button
          onClick={() => {
            mutate();
            mutateEvents();
          }}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-elevated text-white hover:bg-slate-border transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Total Events" value={stats?.total_events} />
        <StatCard label="Processed" value={stats?.processed_count} />
        <StatCard label="Errors" value={stats?.error_count} accent="rose" />
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-lg font-semibold text-white">Events</h3>
            <p className="text-sm text-slate-muted">Latest inbound events for this provider.</p>
          </div>
          <Link href="/admin/webhooks/inbound/events" className="text-sm text-teal-electric hover:text-teal-glow">
            View all
          </Link>
        </div>
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-slate-muted">
              <th className="px-4 py-3">ID</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Received</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-border">
            {(events?.items || events?.data || events || []).map((event: any) => (
              <tr key={event.id}>
                <td className="px-4 py-3 text-white">{event.id}</td>
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
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-white text-xs hover:bg-slate-border"
                    >
                      <Activity className="w-3.5 h-3.5" />
                      Details
                    </Link>
                    <button
                      onClick={() => handleReplay(event.id)}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-xs text-teal-electric hover:text-teal-glow"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Replay
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!events?.length && !events?.items && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-muted">
                  No events yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatCard({ label, value, accent = 'teal' }: { label: string; value?: number; accent?: 'teal' | 'rose' }) {
  const styles =
    accent === 'rose'
      ? { bg: 'bg-rose-500/10', text: 'text-rose-300' }
      : { bg: 'bg-teal-500/10', text: 'text-teal-300' };
  return (
    <div className={cn('border border-slate-border rounded-xl p-4', styles.bg)}>
      <p className="text-sm text-slate-muted">{label}</p>
      <p className={cn('text-2xl font-bold', styles.text)}>{value ?? 0}</p>
    </div>
  );
}
