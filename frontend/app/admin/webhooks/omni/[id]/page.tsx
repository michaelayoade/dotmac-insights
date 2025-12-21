'use client';

import useSWR from 'swr';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { RefreshCw, ArrowLeft, Shield, RotateCcw, Eye } from 'lucide-react';
import { webhooksApi, OmniChannel, OmniChannelWebhookEvent } from '@/lib/api';
import { useToast } from '@dotmac/core';
import { useState } from 'react';
import { cn } from '@/lib/utils';

export default function OmniChannelDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const { toast } = useToast();

  const { data: channel, mutate } = useSWR<OmniChannel | undefined>(
    id ? ['omni-channel', id] : null,
    () => webhooksApi.getOmniChannel(id),
    {}
  );
  const { data: events, mutate: mutateEvents } = useSWR<OmniChannelWebhookEvent[] | undefined>(
    id ? ['omni-channel-events', id] : null,
    () => webhooksApi.getOmniChannelWebhookEvents(id),
    {}
  );
  const [payload, setPayload] = useState<OmniChannelWebhookEvent | null>(null);

  const handleRotate = async () => {
    try {
      await webhooksApi.rotateOmniChannelSecret(id);
      await mutate();
      toast({ title: 'Secret rotated', variant: 'success' });
    } catch (err: any) {
      toast({ title: 'Rotation failed', description: err?.message, variant: 'error' });
    }
  };

  const loadEvent = async (eventId: number) => {
    try {
      const data = await webhooksApi.getOmniChannelWebhookEvent(id, eventId);
      setPayload(data);
    } catch (err: any) {
      toast({ title: 'Failed to load payload', description: err?.message, variant: 'error' });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/admin/webhooks/omni" className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-foreground hover:bg-slate-border">
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>
          <h1 className="text-2xl font-bold text-foreground">{channel?.name || 'Channel'}</h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              mutate();
              mutateEvents();
            }}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-elevated text-foreground hover:bg-slate-border transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={handleRotate}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric text-slate-950 font-medium hover:bg-teal-electric/90"
          >
            <RotateCcw className="w-4 h-4" />
            Rotate Secret
          </button>
        </div>
      </div>

      {channel && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-2">
          <p className="text-sm text-slate-muted">Webhook URL</p>
          <p className="text-foreground text-base">{channel.webhook_url || 'Not configured'}</p>
          <div className="flex items-center gap-2 text-xs text-slate-muted">
            <Shield className="w-3.5 h-3.5" />
            {channel.webhook_secret_configured ? 'Secret configured' : 'Secret missing'}
          </div>
        </div>
      )}

      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-border flex items-center justify-between">
          <p className="text-sm text-slate-muted">Webhook Events</p>
          <button
            onClick={() => mutateEvents()}
            className="text-xs text-slate-muted hover:text-foreground inline-flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
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
            {(events || []).map((event) => (
              <tr key={event.id}>
                <td className="px-4 py-3 text-foreground">{event.id}</td>
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
                    {event.status || 'pending'}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-muted">
                  {event.created_at ? new Date(event.created_at).toLocaleString() : '--'}
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => loadEvent(event.id)}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-foreground text-xs hover:bg-slate-border"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    Payload
                  </button>
                </td>
              </tr>
            ))}
            {!events?.length && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-muted">
                  No events yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {payload && (
        <div className="bg-slate-card border border-slate-border rounded-xl">
          <div className="px-4 py-3 border-b border-slate-border flex items-center justify-between">
            <p className="text-sm text-slate-muted">Event Payload</p>
            <button onClick={() => setPayload(null)} className="text-xs text-slate-muted hover:text-foreground">
              Close
            </button>
          </div>
          <pre className="p-4 text-sm text-slate-100 overflow-auto bg-slate-elevated">
{JSON.stringify(payload, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
