'use client';

import useSWR from 'swr';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, RefreshCw, RotateCcw } from 'lucide-react';
import { api } from '@/lib/api';
import { useToast } from '@dotmac/core';

export default function InboundEventDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const id = Number(params.id);

  const { data, mutate, isLoading } = useSWR(id ? ['webhook-event', id] : null, () => api.getWebhookEvent(id));

  const handleReplay = async () => {
    if (!id) return;
    try {
      await api.replayWebhookEvent(id);
      toast({ title: 'Replay scheduled', variant: 'success' });
      await mutate();
    } catch (err: any) {
      toast({ title: 'Replay failed', description: err?.message, variant: 'error' });
    }
  };

  if (!data && isLoading) {
    return <p className="text-slate-muted">Loading...</p>;
  }

  if (!data) {
    return <p className="text-slate-muted">Event not found.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-white hover:bg-slate-border"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
          <h1 className="text-2xl font-bold text-white">Event {data.id}</h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => mutate()}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-elevated text-white hover:bg-slate-border transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={handleReplay}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric text-slate-950 font-medium hover:bg-teal-electric/90"
          >
            <RotateCcw className="w-4 h-4" />
            Replay
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <InfoCard label="Provider" value={data.provider} />
        <InfoCard label="Event Type" value={data.event_type} />
        <InfoCard label="Status" value={data.status} />
        <InfoCard label="Received" value={data.created_at ? new Date(data.created_at).toLocaleString() : '--'} />
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl">
        <div className="px-4 py-3 border-b border-slate-border flex items-center justify-between">
          <p className="text-sm text-slate-muted">Payload</p>
          <Link href="/admin/webhooks/inbound/events" className="text-xs text-teal-electric hover:text-teal-glow">
            Back to list
          </Link>
        </div>
        <pre className="p-4 text-sm text-slate-100 overflow-auto bg-slate-elevated">
{JSON.stringify((data as any).payload || data, null, 2)}
        </pre>
      </div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4">
      <p className="text-xs text-slate-muted uppercase tracking-wide">{label}</p>
      <p className="text-white text-base mt-1">{value}</p>
    </div>
  );
}
