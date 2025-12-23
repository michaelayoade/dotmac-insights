'use client';

import useSWR from 'swr';
import Link from 'next/link';
import { RefreshCw, Radio, Shield } from 'lucide-react';
import { webhooksApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

type Channel = {
  id: number;
  name: string;
  type: string;
  is_active?: boolean;
  webhook_secret_configured?: boolean;
  webhook_url?: string;
  stats?: {
    total_events?: number;
    processed_events?: number;
    last_event_at?: string;
  };
};

export default function OmniWebhooksPage() {
  const { data, isLoading, mutate } = useSWR<Channel[]>('omni-channels', webhooksApi.getOmniChannels);
  const channels = data || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Omnichannel Webhooks</h1>
          <p className="text-slate-muted">Channel delivery webhooks and secrets.</p>
        </div>
        <Button
          onClick={() => mutate()}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-elevated text-foreground hover:bg-slate-border transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {channels.map((channel) => (
          <Link
            key={channel.id}
            href={`/admin/webhooks/omni/${channel.id}`}
            className="bg-slate-card border border-slate-border rounded-xl p-4 hover:border-slate-elevated transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Radio className="w-5 h-5 text-blue-400" />
                <div>
                  <p className="text-foreground font-semibold">{channel.name}</p>
                  <p className="text-xs text-slate-muted uppercase">{channel.type}</p>
                </div>
              </div>
              <span
                className={cn(
                  'px-2 py-1 rounded-full text-xs font-medium',
                  channel.is_active ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-elevated text-slate-muted'
                )}
              >
                {channel.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <p className="text-xs text-slate-muted mb-2">Webhook: {channel.webhook_url || 'Not configured'}</p>
            <div className="flex items-center gap-2 text-xs text-slate-muted">
              <Shield className="w-3.5 h-3.5" />
              {channel.webhook_secret_configured ? 'Secret configured' : 'Secret missing'}
            </div>
            <div className="mt-2 text-xs text-slate-muted">
              {(channel.stats?.total_events || 0)} events • processed {(channel.stats?.processed_events || 0)}
            </div>
          </Link>
        ))}
        {!channels.length && !isLoading && (
          <div className="col-span-full text-slate-muted text-sm">No channels found.</div>
        )}
      </div>
    </div>
  );
}
