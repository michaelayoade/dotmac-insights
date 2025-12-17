'use client';

import { useMemo, useState } from 'react';
import useSWR from 'swr';
import { Plus, RefreshCw, ExternalLink, Trash2, Zap } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useToast } from '@dotmac/core';

type Webhook = {
  id: number;
  name: string;
  url: string;
  event_types?: string[];
  is_active?: boolean;
  created_at?: string;
};

export default function WebhooksPage() {
  const { toast } = useToast();
  const { data, isLoading, mutate } = useSWR<Webhook[]>('webhooks', api.listWebhooks);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: '', url: '', events: '' });
  const [saving, setSaving] = useState(false);

  const webhooks = data || [];

  const handleCreate = async () => {
    if (!form.name || !form.url) {
      toast({ title: 'Missing fields', description: 'Name and URL are required', variant: 'error' });
      return;
    }
    setSaving(true);
    try {
      await api.createWebhook({
        name: form.name,
        url: form.url,
        event_types: form.events.split(',').map((e) => e.trim()).filter(Boolean),
      });
      setForm({ name: '', url: '', events: '' });
      setCreating(false);
      await mutate();
      toast({ title: 'Webhook created', variant: 'success' });
    } catch (err: any) {
      toast({ title: 'Failed to create webhook', description: err?.message, variant: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this webhook?')) return;
    try {
      await api.deleteWebhook(id);
      await mutate();
      toast({ title: 'Webhook deleted', variant: 'success' });
    } catch (err: any) {
      toast({ title: 'Failed to delete webhook', description: err?.message, variant: 'error' });
    }
  };

  const activeCount = useMemo(() => webhooks.filter((w) => w.is_active !== false).length, [webhooks]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Webhooks</h1>
          <p className="text-slate-muted">Manage outbound webhook subscriptions and secrets.</p>
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
            onClick={() => setCreating(true)}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric text-slate-950 font-medium hover:bg-teal-electric/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Webhook
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total" value={webhooks.length} />
        <StatCard label="Active" value={activeCount} />
        <StatCard label="Inactive" value={webhooks.length - activeCount} />
      </div>

      {/* List */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-border flex items-center justify-between">
          <p className="text-sm text-slate-muted">Outbound Webhooks</p>
          {isLoading && <p className="text-xs text-slate-muted">Loading...</p>}
        </div>
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-slate-muted">
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">URL</th>
              <th className="px-4 py-3">Events</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-border">
            {webhooks.map((webhook) => (
              <tr key={webhook.id}>
                <td className="px-4 py-3 text-white font-medium">{webhook.name}</td>
                <td className="px-4 py-3 text-slate-muted">{webhook.url}</td>
                <td className="px-4 py-3 text-slate-muted">
                  {webhook.event_types?.length ? webhook.event_types.join(', ') : 'All events'}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Link
                      href={`/admin/webhooks/${webhook.id}`}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-white text-xs hover:bg-slate-border"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      View
                    </Link>
                    <button
                      onClick={() => handleDelete(webhook.id)}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-rose-300 text-xs hover:bg-rose-500/20"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!webhooks.length && !isLoading && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-muted">
                  No webhooks configured yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Create panel */}
      {creating && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Create Webhook</h2>
              <p className="text-sm text-slate-muted">Subscribe to webhook events with signing secret support.</p>
            </div>
            <button onClick={() => setCreating(false)} className="text-slate-muted hover:text-white text-sm">
              Cancel
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Field
              label="Name"
              placeholder="Billing Webhooks"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            />
            <Field
              label="URL"
              placeholder="https://example.com/webhooks"
              value={form.url}
              onChange={(e) => setForm((prev) => ({ ...prev, url: e.target.value }))}
            />
            <Field
              label="Events (comma separated)"
              placeholder="invoice.paid, invoice.failed"
              value={form.events}
              onChange={(e) => setForm((prev) => ({ ...prev, events: e.target.value }))}
            />
          </div>

          <div className="flex justify-end gap-2">
            <button
              onClick={handleCreate}
              disabled={saving}
              className={cn(
                'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                saving ? 'bg-slate-elevated text-slate-muted' : 'bg-teal-electric text-slate-950 hover:bg-teal-electric/90'
              )}
            >
              {saving ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Create Webhook
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4">
      <p className="text-sm text-slate-muted">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
    </div>
  );
}

function Field({
  label,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <div className="space-y-2">
      <label className="text-sm text-slate-muted">{label}</label>
      <input
        {...props}
        className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white text-sm focus:border-teal-electric focus:outline-none"
      />
    </div>
  );
}
