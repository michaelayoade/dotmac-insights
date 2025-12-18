'use client';

import { useEffect, useState } from 'react';
import useSWR from 'swr';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, RefreshCw, Save, Shield, ShieldCheck, TestTube, RotateCcw, Trash2, Eye, X } from 'lucide-react';
import { webhooksApi, Webhook, WebhookDelivery } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useToast } from '@dotmac/core';
import Link from 'next/link';

export default function WebhookDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const id = Number(params.id);

  const { data: webhook, mutate } = useSWR<Webhook>(id ? ['webhook', id] : null, ([, webhookId]) =>
    webhooksApi.getWebhook(Number(webhookId))
  );
  const { data: deliveries, mutate: mutateDeliveries } = useSWR<WebhookDelivery[]>(id ? ['webhook-deliveries', id] : null, ([, webhookId]) =>
    webhooksApi
      .getWebhookDeliveries(Number(webhookId), { limit: 50 })
      .then((response) => response.deliveries || response.items || [])
  );

  const [form, setForm] = useState({ name: '', url: '', events: '' });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [payloadView, setPayloadView] = useState<{ id: number; body: unknown } | null>(null);

  useEffect(() => {
    if (webhook) {
      setForm({
        name: webhook.name,
        url: webhook.url,
        events: webhook.event_types?.join(', ') || '',
      });
    }
  }, [webhook]);

  const handleSave = async () => {
    if (!webhook) return;
    setSaving(true);
    try {
      await webhooksApi.updateWebhook(webhook.id, {
        name: form.name,
        url: form.url,
        event_types: form.events.split(',').map((e) => e.trim()).filter(Boolean),
      });
      await mutate();
      toast({ title: 'Webhook updated', variant: 'success' });
    } catch (err: any) {
      toast({ title: 'Failed to update webhook', description: err?.message, variant: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!webhook) return;
    setTesting(true);
    try {
      await webhooksApi.testWebhook(webhook.id);
      toast({ title: 'Test event sent', variant: 'success' });
    } catch (err: any) {
      toast({ title: 'Failed to send test', description: err?.message, variant: 'error' });
    } finally {
      setTesting(false);
    }
  };

  const handleRotate = async () => {
    if (!webhook) return;
    setRotating(true);
    try {
      await webhooksApi.rotateWebhookSecret(webhook.id);
      await mutate();
      toast({ title: 'Signing secret rotated', variant: 'success' });
    } catch (err: any) {
      toast({ title: 'Failed to rotate secret', description: err?.message, variant: 'error' });
    } finally {
      setRotating(false);
    }
  };

  const handleDelete = async () => {
    if (!webhook) return;
    if (!confirm('Delete this webhook?')) return;
    try {
      await webhooksApi.deleteWebhook(webhook.id);
      toast({ title: 'Webhook deleted', variant: 'success' });
      router.push('/admin/webhooks');
    } catch (err: any) {
      toast({ title: 'Failed to delete webhook', description: err?.message, variant: 'error' });
    }
  };

  const handleRetry = async (deliveryId: number) => {
    try {
      await webhooksApi.retryWebhookDelivery(deliveryId);
      await mutateDeliveries();
      toast({ title: 'Retry scheduled', variant: 'success' });
    } catch (err: any) {
      toast({ title: 'Failed to retry delivery', description: err?.message, variant: 'error' });
    }
  };

  const loadPayload = async (deliveryId: number) => {
    try {
      const payload = await webhooksApi.getWebhookDelivery(id, deliveryId);
      setPayloadView({ id: deliveryId, body: payload });
    } catch (err: any) {
      toast({ title: 'Failed to load payload', description: err?.message, variant: 'error' });
    }
  };

  if (!webhook) {
    return (
      <div className="space-y-4">
        <SkeletonHeader />
        <div className="bg-slate-card border border-slate-border rounded-xl p-6 text-slate-muted">Loading webhook...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/admin/webhooks" className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-white hover:bg-slate-border">
          <ArrowLeft className="w-4 h-4" />
          Back
        </Link>
        <h1 className="text-2xl font-bold text-white">{webhook.name}</h1>
        <span className={cn('px-2 py-1 rounded-full text-xs font-medium', webhook.is_active !== false ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-elevated text-slate-muted')}>
          {webhook.is_active !== false ? 'Active' : 'Disabled'}
        </span>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Webhook Details</h2>
              <p className="text-sm text-slate-muted">Update endpoint and event subscriptions.</p>
            </div>
            <button
              onClick={handleSave}
              disabled={saving}
              className={cn(
                'inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                saving ? 'bg-slate-elevated text-slate-muted' : 'bg-teal-electric text-slate-950 hover:bg-teal-electric/90'
              )}
            >
              {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>

          <div className="space-y-4">
            <Field
              label="Name"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            />
            <Field
              label="URL"
              value={form.url}
              onChange={(e) => setForm((prev) => ({ ...prev, url: e.target.value }))}
            />
            <Field
              label="Events (comma separated)"
              value={form.events}
              onChange={(e) => setForm((prev) => ({ ...prev, events: e.target.value }))}
            />
            {webhook.secret_last_rotated_at && (
              <p className="text-xs text-slate-muted">
                Secret last rotated: {new Date(webhook.secret_last_rotated_at).toLocaleString()}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <button
                onClick={handleRotate}
                disabled={rotating}
                className={cn(
                  'inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  rotating ? 'bg-slate-elevated text-slate-muted' : 'bg-slate-elevated text-white hover:bg-slate-border'
                )}
              >
                {rotating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
                Rotate Secret
              </button>
              <button
                onClick={handleTest}
                disabled={testing}
                className={cn(
                  'inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  testing ? 'bg-slate-elevated text-slate-muted' : 'bg-slate-elevated text-white hover:bg-slate-border'
                )}
              >
                {testing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <TestTube className="w-4 h-4" />}
                Send Test
              </button>
              <button
                onClick={handleDelete}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-rose-500/10 text-rose-300 hover:bg-rose-500/20"
              >
                <Trash2 className="w-4 h-4" />
                Delete
              </button>
            </div>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            Delivery Status
          </h3>
          <p className="text-slate-muted text-sm">Monitor recent delivery attempts and retry failures.</p>
          <div className="space-y-2">
            {(deliveries || []).slice(0, 5).map((delivery) => (
              <div
                key={delivery.id}
                className="flex items-center justify-between bg-slate-elevated border border-slate-border rounded-lg px-3 py-2"
              >
                <div>
                  <p className="text-sm text-white">{delivery.event_type || 'event'}</p>
                  <p className="text-xs text-slate-muted">
                    {delivery.status} • {delivery.response_status_code ?? '--'}
                  </p>
                </div>
                {delivery.status !== 'success' && (
                  <button
                    onClick={() => handleRetry(delivery.id)}
                    className="text-xs text-teal-electric hover:text-teal-glow inline-flex items-center gap-1"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    Retry
                  </button>
                )}
              </div>
            ))}
            {!deliveries?.length && <p className="text-sm text-slate-muted">No deliveries yet.</p>}
            <Link href="#deliveries" className="text-xs text-teal-electric hover:text-teal-glow">
              View all deliveries
            </Link>
          </div>
        </div>
      </div>

      <div id="deliveries" className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-border flex items-center justify-between">
          <p className="text-sm text-slate-muted">Delivery History</p>
          <button onClick={() => mutateDeliveries()} className="text-xs text-slate-muted hover:text-white inline-flex items-center gap-1">
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
        </div>
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-slate-muted">
              <th className="px-4 py-3">Event</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Response</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-border">
            {(deliveries || []).map((delivery) => (
              <tr key={delivery.id}>
                <td className="px-4 py-3 text-white">{delivery.event_type || 'event'}</td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      'px-2 py-1 rounded-full text-xs font-medium',
                      delivery.status === 'success'
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-amber-500/10 text-amber-300'
                    )}
                  >
                    {delivery.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-muted">{delivery.response_status_code ?? '--'}</td>
                <td className="px-4 py-3 text-slate-muted">
                  {delivery.created_at ? new Date(delivery.created_at).toLocaleString() : '--'}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => loadPayload(delivery.id)}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-white text-xs hover:bg-slate-border"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      Payload
                    </button>
                    {delivery.status !== 'success' && (
                      <button
                        onClick={() => handleRetry(delivery.id)}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-elevated text-amber-200 text-xs hover:bg-amber-500/20"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        Retry
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!deliveries?.length && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-muted">
                  No deliveries found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {payloadView && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setPayloadView(null)}>
          <div className="bg-slate-card border border-slate-border rounded-xl max-w-4xl w-full max-h-[80vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-border">
              <div>
                <p className="text-sm text-slate-muted">Delivery Payload</p>
                <p className="text-white text-sm">Delivery ID: {payloadView.id}</p>
              </div>
              <button onClick={() => setPayloadView(null)} className="text-slate-muted hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <pre className="p-4 text-sm text-slate-100 overflow-auto bg-slate-elevated h-[60vh]">
{JSON.stringify(payloadView.body, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

function Field(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <div className="space-y-2">
      <label className="text-sm text-slate-muted">{props.label}</label>
      <input
        {...props}
        className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white text-sm focus:border-teal-electric focus:outline-none"
      />
    </div>
  );
}

function SkeletonHeader() {
  return (
    <div className="flex items-center gap-3">
      <div className="h-8 w-24 bg-slate-700 rounded animate-pulse" />
      <div className="h-8 w-32 bg-slate-700 rounded animate-pulse" />
    </div>
  );
}
