'use client';

import { useEffect, useState } from 'react';
import {
  ShieldCheck,
  Lock,
  Unlock,
  CalendarRange,
  Globe2,
  RefreshCcw,
  Landmark,
  Banknote,
  Bell,
  FileDown,
  ClipboardList,
  Plus,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useFiscalPeriods,
  useFiscalPeriodMutations,
  useAccountingPendingApprovals,
  useAccountingWorkflows,
  useAccountingWorkflowMutations,
  useExchangeRates,
  useExchangeRatesLatest,
  useExchangeRateMutations,
  useAccountingControls,
  useAccountingControlMutations,
  useAuditLog,
  useFxRevaluationHistory,
  useFxRevaluationMutations,
} from '@/hooks/useApi';
import { DashboardShell, PageHeader, Button, SectionHeader } from '@/components/ui';
import { formatAccountingCurrency } from '@/lib/formatters/accounting';

export default function BooksControlsPage() {
  const { data: periods, error: periodsError, isLoading: periodsLoading, mutate: refetchPeriods } = useFiscalPeriods();
  const { closePeriod, reopenPeriod, generateClosingEntries, createPeriods } = useFiscalPeriodMutations();
  const { data: approvals, error: approvalsError, isLoading: approvalsLoading, mutate: refetchApprovals } = useAccountingPendingApprovals();
  const { data: workflows, error: workflowsError, isLoading: workflowsLoading, mutate: refetchWorkflows } = useAccountingWorkflows();
  const { createWorkflow } = useAccountingWorkflowMutations();
  const { data: rates, error: ratesError, isLoading: ratesLoading, mutate: refetchRates } = useExchangeRates();
  const { data: latestRates } = useExchangeRatesLatest();
  const { createRate } = useExchangeRateMutations();
  const { data: controls, error: controlsError, isLoading: controlsLoading, mutate: refetchControls } = useAccountingControls();
  const { updateControls } = useAccountingControlMutations();
  const { data: auditLog, error: auditError, isLoading: auditLoading, mutate: refetchAudit } = useAuditLog({ limit: 10 });
  const { data: revalHistory, error: revalError, isLoading: revalLoading, mutate: refetchReval } = useFxRevaluationHistory();
  const { preview, apply } = useFxRevaluationMutations();

  const [newWorkflowName, setNewWorkflowName] = useState('');
  const [newRate, setNewRate] = useState({ pair: 'USD/NGN', rate: '', date: '' });
  const [periodForm, setPeriodForm] = useState({ fiscal_year: '', frequency: 'monthly' });
  const [controlForm, setControlForm] = useState({
    auto_posting: controls?.auto_posting ?? true,
    allow_backdated_entries: controls?.allow_backdated_entries ?? false,
  });
  const [revalForm, setRevalForm] = useState({ start_date: '', end_date: '', currency: 'NGN' });
  const [revalResult, setRevalResult] = useState<any>(null);

  useEffect(() => {
    if (controls) {
      setControlForm({
        auto_posting: controls.auto_posting ?? true,
        allow_backdated_entries: controls.allow_backdated_entries ?? false,
      });
    }
  }, [controls]);

  // Aggregate loading and error states
  const isLoading = periodsLoading || approvalsLoading || workflowsLoading || ratesLoading || controlsLoading || auditLoading || revalLoading;
  const firstError = periodsError || approvalsError || workflowsError || ratesError || controlsError || auditError || revalError;
  const retryAll = () => {
    refetchPeriods();
    refetchApprovals();
    refetchWorkflows();
    refetchRates();
    refetchControls();
    refetchAudit();
    refetchReval();
  };

  return (
    <DashboardShell
      isLoading={isLoading}
      error={firstError}
      onRetry={retryAll}
      loadingMessage="Loading accounting controls..."
    >
      <div className="space-y-6">
        <PageHeader
          title="Books Controls"
          subtitle="Period close, approvals, FX, tax, banking, and dunning operations"
          icon={ShieldCheck}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card title="Period Close" icon={ShieldCheck}>
            <div className="space-y-3">
              {!periods?.length ? (
                <p className="text-slate-muted text-sm">No fiscal periods</p>
              ) : (
                periods.map((p: any) => (
                  <div key={p.id || p.name} className="flex items-center justify-between border border-slate-border rounded-lg p-3">
                    <div>
                      <p className="text-foreground font-medium">{p.name || p.label}</p>
                      <p className="text-slate-muted text-sm flex items-center gap-2">
                        <CalendarRange className="w-4 h-4" />
                        {p.start_date || p.start} → {p.end_date || p.end}
                      </p>
                      {p.status === 'closed' && p.closed_by && (
                        <p className="text-xs text-slate-muted mt-1">Closed by {p.closed_by} on {p.closed_at}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          'px-3 py-1 rounded-full text-xs font-semibold border',
                          p.status === 'closed'
                            ? 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10'
                            : 'text-yellow-300 border-yellow-500/40 bg-yellow-500/10'
                        )}
                      >
                        {p.status === 'closed' ? 'Closed' : 'Open'}
                      </span>
                      {p.status === 'closed' ? (
                        <Button variant="secondary" size="sm" onClick={() => reopenPeriod(p.id)}>
                          <Unlock className="w-4 h-4 inline mr-1" /> Reopen
                        </Button>
                      ) : (
                        <Button variant="primary" size="sm" onClick={() => closePeriod(p.id)}>
                          <Lock className="w-4 h-4 inline mr-1" /> Close
                        </Button>
                      )}
                      <Button variant="secondary" size="sm" onClick={() => generateClosingEntries(p.id)}>
                        Run closing
                      </Button>
                    </div>
                  </div>
                ))
              )}
              <div className="flex flex-wrap gap-2 items-end">
                <input
                  value={periodForm.fiscal_year}
                  onChange={(e) => setPeriodForm((prev) => ({ ...prev, fiscal_year: e.target.value }))}
                  placeholder="Fiscal year (e.g. 2025)"
                  className="input-field"
                />
                <select
                  value={periodForm.frequency}
                  onChange={(e) => setPeriodForm((prev) => ({ ...prev, frequency: e.target.value }))}
                  className="input-field"
                >
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                </select>
                <Button variant="primary" size="sm" icon={Plus} onClick={() => createPeriods({ fiscal_year: periodForm.fiscal_year, frequency: periodForm.frequency })}>
                  Create periods
                </Button>
              </div>
            </div>
          </Card>

          <Card title="Approvals" icon={ClipboardList}>
            <div className="space-y-3">
              {!approvals?.length ? (
                <p className="text-slate-muted text-sm">No pending approvals</p>
              ) : (
                approvals.map((row: any) => (
                  <div key={row.id} className="border border-slate-border rounded-lg p-3 flex items-center justify-between">
                    <div>
                      <p className="text-foreground font-medium">{row.document_number || row.document_id || row.id}</p>
                      <p className="text-slate-muted text-sm">
                        {row.doctype} · {formatAccountingCurrency(row.amount ?? 0, row.currency || 'NGN')}
                      </p>
                      <p className="text-slate-muted text-xs">By {row.requested_by || row.created_by}</p>
                    </div>
                    <span className="text-slate-muted text-xs uppercase">{row.status || 'Pending'}</span>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card title="FX Revaluation" icon={RefreshCcw}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <input
                value={revalForm.start_date}
                onChange={(e) => setRevalForm((p) => ({ ...p, start_date: e.target.value }))}
                placeholder="Start date"
                type="date"
                className="input-field"
              />
              <input
                value={revalForm.end_date}
                onChange={(e) => setRevalForm((p) => ({ ...p, end_date: e.target.value }))}
                placeholder="End date"
                type="date"
                className="input-field"
              />
              <input
                value={revalForm.currency}
                onChange={(e) => setRevalForm((p) => ({ ...p, currency: e.target.value }))}
                placeholder="Currency"
                className="input-field"
              />
            </div>
            <div className="flex gap-2 mt-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={async () => {
                  const res = await preview(revalForm);
                  setRevalResult(res);
                }}
              >
                Preview
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={async () => {
                  const res = await apply(revalForm);
                  setRevalResult(res);
                }}
              >
                Apply
              </Button>
            </div>
            {revalResult && (
              <div className="mt-3 bg-slate-elevated border border-slate-border rounded-lg p-3 text-xs text-slate-100 overflow-x-auto">
                <pre className="whitespace-pre-wrap">
                  {typeof revalResult === 'string' ? revalResult : JSON.stringify(revalResult, null, 2)}
                </pre>
              </div>
            )}
            {revalHistory && (
              <div className="mt-3">
                <p className="text-xs uppercase tracking-[0.1em] text-slate-muted mb-2">Recent runs</p>
                <Table
                  columns={['Period', 'Currency', 'Status']}
                  rows={(revalHistory.data || revalHistory || []).map((row: any) => [
                    `${row.start_date || ''} → ${row.end_date || ''}`,
                    row.currency || 'NGN',
                    row.status || 'Completed',
                  ])}
                  empty="No revaluation history"
                />
              </div>
            )}
          </Card>

          <Card title="FX Rates" icon={Globe2}>
            <Table
              columns={['Pair', 'Rate', 'Date']}
              rows={(rates || []).map((r: any) => [r.pair || `${r.from_currency}/${r.to_currency}`, r.rate, r.date])}
              empty="No rates"
            />
            <div className="mt-3 space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <input
                  value={newRate.pair}
                  onChange={(e) => setNewRate((p) => ({ ...p, pair: e.target.value }))}
                  className="input-field"
                  placeholder="Pair (e.g. USD/NGN)"
                />
                <input
                  value={newRate.rate}
                  onChange={(e) => setNewRate((p) => ({ ...p, rate: e.target.value }))}
                  className="input-field"
                  placeholder="Rate"
                />
                <input
                  value={newRate.date}
                  onChange={(e) => setNewRate((p) => ({ ...p, date: e.target.value }))}
                  className="input-field"
                  placeholder="Date (optional)"
                />
              </div>
              <Button
                variant="secondary"
                size="sm"
                icon={RefreshCcw}
                onClick={() => createRate({ pair: newRate.pair, rate: Number(newRate.rate), date: newRate.date || undefined })}
              >
                Add rate
              </Button>
            </div>
            {latestRates && (
              <p className="text-xs text-slate-muted mt-2">
                Latest: {latestRates.pair || latestRates.from_currency} @ {latestRates.rate} on {latestRates.date}
              </p>
            )}
          </Card>

          <Card title="Tax Filing" icon={Landmark}>
            <p className="text-slate-muted text-sm">Use tax reports and controls to manage filings.</p>
          </Card>

          <Card title="Bank Reconciliation" icon={Banknote}>
            <p className="text-slate-muted text-sm">Reconciliation status via banking module.</p>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card title="Dunning & Credit Control" icon={Bell}>
            <p className="text-slate-muted text-sm">Automated reminders and holds coming from AR aging.</p>
            <div className="mt-3 flex gap-2">
              <Button variant="primary" size="sm">Send reminders</Button>
              <Button variant="secondary" size="sm">Review holds</Button>
            </div>
          </Card>

          <Card title="Workflow & Audit" icon={FileDown}>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <input
                  value={newWorkflowName}
                  onChange={(e) => setNewWorkflowName(e.target.value)}
                  placeholder="Workflow name"
                  className="input-field flex-1"
                />
                <Button
                  variant="primary"
                  size="sm"
                  icon={Plus}
                  onClick={() => {
                    if (newWorkflowName) createWorkflow({ name: newWorkflowName });
                  }}
                >
                  Add workflow
                </Button>
              </div>
              {!workflows?.length ? (
                <p className="text-slate-muted text-sm">No workflows</p>
              ) : (
                <Table
                  columns={['Workflow', 'Steps']}
                  rows={workflows.map((w: any) => [w.name, w.steps?.length || 0])}
                  empty="No workflows"
                />
              )}
            </div>
            <div className="mt-4">
              <h4 className="text-sm text-foreground font-semibold mb-2">Audit Log</h4>
              <Table
                columns={['When', 'User', 'Action', 'Doc']}
                rows={(auditLog?.data || auditLog || []).map((log: any) => [
                  log.timestamp || log.created_at,
                  log.user || log.owner,
                  log.action || log.event,
                  `${log.doctype || ''} ${log.document_id || ''}`,
                ])}
                empty="No audit entries"
              />
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card title="Accounting Controls" icon={ShieldCheck}>
            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={!!controlForm.auto_posting}
                  onChange={(e) => setControlForm((prev) => ({ ...prev, auto_posting: e.target.checked }))}
                />
                <span className="text-slate-200 text-sm">Auto-posting to GL</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={!!controlForm.allow_backdated_entries}
                  onChange={(e) => setControlForm((prev) => ({ ...prev, allow_backdated_entries: e.target.checked }))}
                />
                <span className="text-slate-200 text-sm">Allow backdated entries</span>
              </label>
              <Button variant="primary" size="sm" icon={RefreshCcw} onClick={() => updateControls(controlForm)}>
                Update controls
              </Button>
            </div>
          </Card>

          <Card title="Notifications" icon={Bell}>
            <p className="text-slate-muted text-sm">Configure approval, dunning, and period-close notifications.</p>
          </Card>
        </div>
      </div>
    </DashboardShell>
  );
}

function Card({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-teal-electric" />
        <h2 className="text-foreground font-semibold text-sm">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function Table({
  columns,
  rows,
  empty,
}: {
  columns: string[];
  rows: (string | number)[][];
  empty: string;
}) {
  if (!rows.length) {
    return <p className="text-slate-muted text-sm">{empty}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-slate-muted">
          <tr>
            {columns.map((c) => (
              <th key={c} className="text-left px-2 py-1.5">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx} className={cn('border-t border-slate-border/60', idx === 0 && 'border-t-0')}>
              {row.map((cell, j) => (
                <td key={j} className="px-2 py-2 text-slate-200">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
