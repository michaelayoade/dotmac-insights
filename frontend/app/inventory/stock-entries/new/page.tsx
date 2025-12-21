'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, CheckCircle2, Plus, Save } from 'lucide-react';
import { useInventoryStockEntryCreate } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

export default function InventoryStockEntryCreatePage() {
  const router = useRouter();
  const { createStockEntry } = useInventoryStockEntryCreate();
  const [entryType, setEntryType] = useState<'material_receipt' | 'material_issue' | 'material_transfer'>('material_receipt');
  const [postingDate, setPostingDate] = useState('');
  const [company, setCompany] = useState('Dotmac');
  const [remarks, setRemarks] = useState('');
  const [lines, setLines] = useState([
    { item_code: '', qty: 1, uom: 'Nos', s_warehouse: '', t_warehouse: '', rate: '', serial_nos: '' },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const updateLine = (index: number, field: string, value: string) => {
    setLines((prev) =>
      prev.map((line, idx) => (idx === index ? { ...line, [field]: value } : line))
    );
  };

  const addLine = () => {
    setLines((prev) => [...prev, { item_code: '', qty: 1, uom: 'Nos', s_warehouse: '', t_warehouse: '', rate: '', serial_nos: '' }]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createStockEntry({
        entry_type: entryType,
        posting_date: postingDate || undefined,
        company: company || undefined,
        remarks: remarks || undefined,
        lines: lines.map((line) => ({
          item_code: line.item_code,
          qty: Number(line.qty) || 0,
          uom: line.uom || 'Nos',
          s_warehouse: line.s_warehouse || null,
          t_warehouse: line.t_warehouse || null,
          rate: line.rate ? Number(line.rate) : undefined,
          serial_nos: line.serial_nos ? line.serial_nos.split(',').map((s) => s.trim()).filter(Boolean) : undefined,
        })),
      });
      setSuccess(true);
      setTimeout(() => router.push('/inventory'), 800);
    } catch (err: any) {
      setError(err?.message || 'Failed to create stock entry');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/inventory"
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Link>
        <h1 className="text-xl font-semibold text-foreground">New Stock Entry</h1>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="bg-green-500/10 border border-green-500/30 text-green-400 rounded-lg p-3 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          <span>Stock entry created</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Entry Type</label>
            <select
              value={entryType}
              onChange={(e) => setEntryType(e.target.value as typeof entryType)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value="material_receipt">Material Receipt</option>
              <option value="material_issue">Material Issue</option>
              <option value="material_transfer">Material Transfer</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Posting Date</label>
            <input
              type="date"
              value={postingDate}
              onChange={(e) => setPostingDate(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Company</label>
            <input
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <div className="space-y-1 md:col-span-3">
            <label className="text-sm text-slate-muted">Remarks</label>
            <input
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-foreground font-semibold">Lines</h3>
            <button
              type="button"
              onClick={addLine}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
            >
              <Plus className="w-4 h-4" />
              Add Line
            </button>
          </div>
          <div className="space-y-3">
            {lines.map((line, idx) => (
              <div key={idx} className="grid grid-cols-1 md:grid-cols-3 gap-3 bg-slate-elevated/60 border border-slate-border/60 rounded-lg p-3">
                <input
                  placeholder="Item Code"
                  value={line.item_code}
                  onChange={(e) => updateLine(idx, 'item_code', e.target.value)}
                  className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  required
                />
                <input
                  type="number"
                  placeholder="Qty"
                  value={line.qty}
                  onChange={(e) => updateLine(idx, 'qty', e.target.value)}
                  className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  required
                />
                <input
                  placeholder="UOM"
                  value={line.uom}
                  onChange={(e) => updateLine(idx, 'uom', e.target.value)}
                  className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  required
                />
                <input
                  placeholder="Source Warehouse"
                  value={line.s_warehouse}
                  onChange={(e) => updateLine(idx, 's_warehouse', e.target.value)}
                  className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
                <input
                  placeholder="Target Warehouse"
                  value={line.t_warehouse}
                  onChange={(e) => updateLine(idx, 't_warehouse', e.target.value)}
                  className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
                <input
                  placeholder="Rate"
                  value={line.rate}
                  onChange={(e) => updateLine(idx, 'rate', e.target.value)}
                  className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
                <input
                  placeholder="Serial Nos (comma separated)"
                  value={line.serial_nos}
                  onChange={(e) => updateLine(idx, 'serial_nos', e.target.value)}
                  className="md:col-span-3 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
            ))}
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className={cn(
            'inline-flex items-center gap-2 px-4 py-2 rounded-md border border-teal-electric/50 text-sm text-teal-electric hover:text-teal-glow hover:border-teal-electric/70',
            submitting && 'opacity-70 cursor-not-allowed'
          )}
        >
          <Save className="w-4 h-4" />
          {submitting ? 'Saving...' : 'Create Stock Entry'}
        </button>
      </form>
    </div>
  );
}
