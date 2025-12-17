'use client';

import useSWR from 'swr';
import Link from 'next/link';
import { RefreshCw, Globe2, BarChart3 } from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

type Provider = {
  name: string;
  display_name: string;
  webhook_url: string;
  secret_configured?: boolean;
  events_supported?: string[];
  stats?: {
    total_events?: number;
    processed_count?: number;
    error_count?: number;
    success_rate?: number;
    last_received?: string;
  };
};

export default function InboundWebhooksPage() {
  const { data, isLoading, mutate } = useSWR<{ providers: Provider[] }>('webhook-providers', api.getWebhookProviders);
  const providers = data?.providers || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Inbound Webhooks</h1>
          <p className="text-slate-muted">Payments and provider webhooks coming into the platform.</p>
        </div>
        <button
          onClick={() => mutate()}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-elevated text-white hover:bg-slate-border transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {providers.map((provider) => (
          <Link
            key={provider.name}
            href={`/admin/webhooks/inbound/providers/${provider.name}`}
            className="bg-slate-card border border-slate-border rounded-xl p-4 hover:border-slate-elevated transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Globe2 className="w-5 h-5 text-teal-electric" />
                <h3 className="text-lg font-semibold text-white">{provider.display_name || provider.name}</h3>
              </div>
              <span
                className={cn(
                  'px-2 py-1 rounded-full text-xs font-medium',
                  provider.secret_configured ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/10 text-amber-300'
                )}
              >
                {provider.secret_configured ? 'Secret configured' : 'Secret missing'}
              </span>
            </div>
            <p className="text-sm text-slate-muted mb-3">{provider.webhook_url}</p>
            <div className="flex items-center gap-3 text-xs text-slate-muted">
              <span>{provider.events_supported?.length || 0} events</span>
              <span>•</span>
              <span>{provider.stats?.total_events || 0} events received</span>
            </div>
            {provider.stats?.last_received && (
              <p className="text-xs text-slate-muted mt-2">
                Last received: {new Date(provider.stats.last_received).toLocaleString()}
              </p>
            )}
          </Link>
        ))}
        {!providers.length && !isLoading && (
          <div className="col-span-full text-slate-muted text-sm">No providers found.</div>
        )}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-2">
          <BarChart3 className="w-5 h-5 text-blue-400" />
          <h3 className="text-sm font-semibold text-white">Recent Events</h3>
        </div>
        <p className="text-sm text-slate-muted mb-2">
          View and replay inbound webhook events.
        </p>
        <Link href="/admin/webhooks/inbound/events" className="text-teal-electric hover:text-teal-glow text-sm">
          Go to events →
        </Link>
      </div>
    </div>
  );
}
