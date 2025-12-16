'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, Calendar as CalendarIcon, Hash, Plus, Trash2, Save } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useJournalEntryAdminMutations, useAccountingChartOfAccounts } from '@/hooks/useApi';
import { AccountSearch } from '@/components/EntitySearch';

type Line = { account: string; description: string; debit: number; credit: number; cost_center: string };
type SelectedAccount = { name: string; account_number?: string } | null;

export default function NewJournalEntryPage() {
  const router = useRouter();
  const { create, submit, approve } = useJournalEntryAdminMutations();
  const { data: accountsData, isLoading: accountsLoading } = useAccountingChartOfAccounts();
  const accounts = useMemo(() => (accountsData as any)?.accounts || accountsData || [], [accountsData]);

  const [form, setForm] = useState({
    reference: '',
    posting_date: '',
    currency: 'NGN',
    memo: '',
  });
  const [lines, setLines] = useState<Line[]>([
    { account: '', description: '', debit: 0, credit: 0, cost_center: '' },
    { account: '', description: '', debit: 0, credit: 0, cost_center: '' },
  ]);
  const [selectedAccounts, setSelectedAccounts] = useState<SelectedAccount[]>([null, null]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleLineChange = (idx: number, field: keyof Line, value: string) => {
    const updated = [...lines];
    if (field === 'debit' || field === 'credit') {
      updated[idx][field] = Number(value) || 0;
    } else {
      updated[idx][field] = value;
    }
    setLines(updated);
  };

  const handleAccountSelect = (idx: number, account: SelectedAccount) => {
    const updatedAccounts = [...selectedAccounts];
    updatedAccounts[idx] = account;
    setSelectedAccounts(updatedAccounts);

    // Update line account value
    const updated = [...lines];
    if (account) {
      updated[idx].account = account.account_number
        ? `${account.account_number} - ${account.name}`
        : account.name;
    } else {
      updated[idx].account = '';
    }
    setLines(updated);
  };

  const addLine = () => {
    setLines((prev) => [...prev, { account: '', description: '', debit: 0, credit: 0, cost_center: '' }]);
    setSelectedAccounts((prev) => [...prev, null]);
  };

  const removeLine = (idx: number) => {
    setLines((prev) => prev.filter((_, i) => i !== idx));
    setSelectedAccounts((prev) => prev.filter((_, i) => i !== idx));
  };

  const totals = useMemo(() => {
    const debit = lines.reduce((acc, line) => acc + (line.debit || 0), 0);
    const credit = lines.reduce((acc, line) => acc + (line.credit || 0), 0);
    return { debit, credit, balanced: Math.abs(debit - credit) < 0.01 };
  }, [lines]);

  const validate = () => {
    if (!form.posting_date) return 'Posting date is required';
    if (!lines.length) return 'Add at least one line';
    if (!totals.balanced) return 'Entry must balance (debits = credits)';
    if (lines.some((l) => !l.account)) return 'Each line needs an account';
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const created = await create({
        posting_date: form.posting_date,
        reference: form.reference || undefined,
        remarks: form.memo || undefined,
        currency: form.currency || 'NGN',
        accounts: lines.map((line) => ({
          account: line.account,
          debit: line.debit || 0,
          credit: line.credit || 0,
          cost_center: line.cost_center || undefined,
          description: line.description || undefined,
        })),
      } as any);
      const id = created?.id ?? created?.name ?? created?.docname;
      if (id) {
        try {
          await submit(id);
          await approve(id);
        } catch (err) {
          // If submit/approve fail, still redirect to list; user can review
          console.warn('Submit/approve failed', err);
        }
      }
      router.push('/books/journal-entries');
    } catch (err: any) {
      setError(err?.message || 'Failed to create journal entry');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books/journal-entries"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to journal entries
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">New Journal Entry</p>
            <h1 className="text-xl font-semibold text-white">Record Journal Entry</h1>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Posting Date" name="posting_date" value={form.posting_date} onChange={handleChange} type="date" required icon={<CalendarIcon className="w-4 h-4 text-slate-muted" />} />
            <Input label="Reference" name="reference" value={form.reference} onChange={handleChange} placeholder="Ref # or source" />
            <Input label="Currency" name="currency" value={form.currency} onChange={handleChange} />
            <Input label="Memo" name="memo" value={form.memo} onChange={handleChange} />
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white font-semibold">Lines</p>
              <p className="text-xs text-slate-muted">Accounts must balance (debits = credits)</p>
            </div>
            <button
              type="button"
              onClick={addLine}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-white hover:bg-slate-elevated"
            >
              <Plus className="w-4 h-4" />
              Add line
            </button>
          </div>
          <div className="space-y-3">
            {lines.map((line, idx) => (
              <div key={idx} className="grid grid-cols-1 md:grid-cols-[1.5fr_2fr_1fr_1fr_1fr_auto] gap-3 items-start bg-slate-elevated border border-slate-border rounded-lg p-3">
                <AccountSearch
                  label="Account"
                  accounts={accounts}
                  value={selectedAccounts[idx]}
                  onSelect={(account) => handleAccountSelect(idx, account)}
                  loading={accountsLoading}
                  required
                />
                <Input
                  label="Description"
                  name={`desc-${idx}`}
                  value={line.description}
                  onChange={(e) => handleLineChange(idx, 'description', e.target.value)}
                  placeholder="Narration"
                />
                <Input
                  label="Debit"
                  name={`debit-${idx}`}
                  value={line.debit}
                  onChange={(e) => handleLineChange(idx, 'debit', e.target.value)}
                  type="number"
                  min={0}
                  icon={<Hash className="w-4 h-4 text-slate-muted" />}
                />
                <Input
                  label="Credit"
                  name={`credit-${idx}`}
                  value={line.credit}
                  onChange={(e) => handleLineChange(idx, 'credit', e.target.value)}
                  type="number"
                  min={0}
                  icon={<Hash className="w-4 h-4 text-slate-muted" />}
                />
                <Input
                  label="Cost Center"
                  name={`cc-${idx}`}
                  value={line.cost_center}
                  onChange={(e) => handleLineChange(idx, 'cost_center', e.target.value)}
                  placeholder="Optional"
                />
                <div className="flex justify-end pt-6">
                  <button
                    type="button"
                    onClick={() => removeLine(idx)}
                    className="p-2 text-slate-muted hover:text-coral-alert hover:bg-slate-card rounded-lg"
                    aria-label="Remove line"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-[2fr_1fr] gap-6">
          <div className="space-y-2">
            <p className="text-sm text-white font-semibold">Summary</p>
            <p className="text-xs text-slate-muted">Debits must equal credits before posting.</p>
          </div>
          <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 space-y-2">
            <TotalRow label="Debits" value={totals.debit} />
            <TotalRow label="Credits" value={totals.credit} />
            <hr className="border-slate-border/60" />
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-muted">Balance</span>
              <span className={cn('font-mono', totals.balanced ? 'text-emerald-300' : 'text-amber-300')}>
                {(totals.debit - totals.credit).toFixed(2)}
              </span>
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-300 rounded-lg p-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex justify-end gap-3">
          <Link
            href="/books/journal-entries"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Posting...' : 'Post Journal Entry'}
          </button>
        </div>
      </form>
    </div>
  );
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string; icon?: React.ReactNode }) {
  const { label, icon, ...rest } = props;
  return (
    <div className="space-y-1.5">
      <label className="block text-sm text-slate-muted">{label}</label>
      <div className="relative">
        {icon && <div className="absolute left-3 top-1/2 -translate-y-1/2">{icon}</div>}
        <input
          {...rest}
          className={cn('input-field', icon && 'pl-9')}
        />
      </div>
    </div>
  );
}

function TotalRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-muted">{label}</span>
      <span className="font-mono text-white">{value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
    </div>
  );
}
