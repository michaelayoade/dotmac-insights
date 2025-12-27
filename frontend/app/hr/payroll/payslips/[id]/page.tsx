'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useHrSalarySlipDetail, useHrSalarySlipMutations } from '@/hooks/useApi';
import { cn, formatCurrency, formatDate } from '@/lib/utils';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { Button, StatusPill, LoadingState, BackButton } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import {
  User,
  Building2,
  Calendar,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Wallet2,
  CheckCircle2,
  XCircle,
  Clock,
  Send,
  Ban,
  Printer,
  AlertTriangle,
  Briefcase,
  CreditCard,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { HrSalaryStructureLine } from '@/lib/api';

function StatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, { tone: StatusTone; icon: LucideIcon }> = {
    paid: { tone: 'success', icon: CheckCircle2 },
    submitted: { tone: 'info', icon: CheckCircle2 },
    void: { tone: 'danger', icon: XCircle },
    cancelled: { tone: 'danger', icon: XCircle },
    draft: { tone: 'warning', icon: Clock },
  };
  const config = statusConfig[status.toLowerCase()] || statusConfig.draft;
  return (
    <StatusPill
      label={formatStatusLabel(status || 'draft')}
      tone={config.tone}
      icon={config.icon}
      className="border border-current/30 text-base px-3 py-1"
    />
  );
}

function SummaryItem({ icon: Icon, label, value, className }: { icon: LucideIcon; label: string; value: string | number; className?: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 rounded-lg bg-slate-elevated flex items-center justify-center">
        <Icon className={cn('w-5 h-5', className || 'text-slate-muted')} />
      </div>
      <div>
        <p className="text-xs text-slate-muted">{label}</p>
        <p className="text-foreground font-medium">{value}</p>
      </div>
    </div>
  );
}

export default function PayslipDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;

  const { isLoading: authLoading, missingScope, hasScope } = useRequireScope('hr:read');
  const canWrite = hasScope('hr:write');

  const { data: slip, isLoading, mutate } = useHrSalarySlipDetail(id);
  const { markPaid } = useHrSalarySlipMutations();

  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showVoidModal, setShowVoidModal] = useState(false);
  const [voidReason, setVoidReason] = useState('');

  const handleMarkPaid = async () => {
    setActionLoading(true);
    setError(null);
    try {
      await markPaid(id, {});
      mutate();
    } catch (err: any) {
      setError(err?.message || 'Failed to mark as paid');
    } finally {
      setActionLoading(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  // Permission guard
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the hr:read permission to view salary slips."
        backHref="/hr/payroll/payslips"
        backLabel="Back to Payslips"
      />
    );
  }

  if (isLoading) {
    return <LoadingState message="Loading salary slip..." />;
  }

  if (!slip) {
    return (
      <div className="space-y-6">
        <BackButton href="/hr/payroll/payslips" label="Payslips" />
        <div className="bg-slate-card border border-slate-border rounded-xl p-8 text-center">
          <XCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <h3 className="text-foreground font-semibold mb-1">Salary Slip Not Found</h3>
          <p className="text-slate-muted text-sm">The requested salary slip could not be found.</p>
        </div>
      </div>
    );
  }

  const earnings: HrSalaryStructureLine[] = slip.earnings || [];
  const deductions: HrSalaryStructureLine[] = slip.deductions || [];
  const totalEarnings = earnings.reduce<number>(
    (sum, e) => sum + (e.amount || e.default_amount || 0),
    0
  );
  const totalDeductions = deductions.reduce<number>(
    (sum, d) => sum + (d.amount || d.default_amount || 0),
    0
  );
  const currency = slip.currency || 'NGN';
  const isDraft = slip.status?.toLowerCase() === 'draft';
  const isSubmitted = slip.status?.toLowerCase() === 'submitted';
  const isPaid = slip.status?.toLowerCase() === 'paid';

  return (
    <div className="space-y-6 print:p-8">
      {/* Header */}
      <div className="flex items-center justify-between print:hidden">
        <div className="flex items-center gap-3">
          <BackButton href="/hr/payroll/payslips" label="Payslips" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Salary Slip</p>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold text-foreground">#{slip.id}</h1>
              <StatusBadge status={slip.status || 'draft'} />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={handlePrint} className="flex items-center gap-2">
            <Printer className="w-4 h-4" />
            Print
          </Button>
          {canWrite && isSubmitted && (
            <Button
              onClick={handleMarkPaid}
              disabled={actionLoading}
              loading={actionLoading}
              className="bg-green-600 hover:bg-green-700 flex items-center gap-2"
            >
              <CheckCircle2 className="w-4 h-4" />
              Mark as Paid
            </Button>
          )}
        </div>
      </div>

      {/* Print Header */}
      <div className="hidden print:block text-center mb-8">
        <h1 className="text-2xl font-bold">Salary Slip</h1>
        <p className="text-gray-600">#{slip.id}</p>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2 print:hidden">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      {/* Employee Info Card */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6 print:border-gray-300">
        <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
          <User className="w-5 h-5 text-violet-400" />
          Employee Information
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <SummaryItem
            icon={User}
            label="Employee"
            value={slip.employee_name || slip.employee || '-'}
            className="text-violet-400"
          />
          <SummaryItem
            icon={Building2}
            label="Department"
            value={slip.department || '-'}
            className="text-blue-400"
          />
          <SummaryItem
            icon={Briefcase}
            label="Designation"
            value={slip.designation || '-'}
            className="text-teal-electric"
          />
          <SummaryItem
            icon={CreditCard}
            label="Bank Account"
            value={slip.bank_account_no || '-'}
            className="text-orange-400"
          />
        </div>
      </div>

      {/* Pay Period Card */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6 print:border-gray-300">
        <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
          <Calendar className="w-5 h-5 text-teal-electric" />
          Pay Period
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <SummaryItem
            icon={Calendar}
            label="Start Date"
            value={formatDate(slip.start_date)}
            className="text-teal-electric"
          />
          <SummaryItem
            icon={Calendar}
            label="End Date"
            value={formatDate(slip.end_date)}
            className="text-teal-electric"
          />
          <SummaryItem
            icon={Calendar}
            label="Posting Date"
            value={formatDate(slip.posting_date)}
            className="text-violet-400"
          />
          <SummaryItem
            icon={Clock}
            label="Payment Days"
            value={slip.payment_days || slip.total_working_days || '-'}
            className="text-blue-400"
          />
        </div>
      </div>

      {/* Earnings & Deductions */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Earnings */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6 print:border-gray-300">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-green-400" />
            Earnings
          </h2>
          <div className="space-y-3">
            {earnings.length === 0 ? (
              <p className="text-slate-muted text-sm">No earnings recorded</p>
            ) : (
              earnings.map((e, idx) => (
                <div key={idx} className="flex items-center justify-between py-2 border-b border-slate-border last:border-0">
                  <div>
                    <p className="text-foreground font-medium">{e.salary_component}</p>
                    {e.abbr && <p className="text-xs text-slate-muted">{e.abbr}</p>}
                  </div>
                  <p className="text-green-400 font-semibold">
                    {formatCurrency(e.amount || e.default_amount || 0, currency)}
                  </p>
                </div>
              ))
            )}
            <div className="flex items-center justify-between pt-3 border-t border-slate-border">
              <p className="text-foreground font-semibold">Total Earnings</p>
              <p className="text-green-400 font-bold text-lg">
                {formatCurrency(totalEarnings || slip.gross_pay || 0, currency)}
              </p>
            </div>
          </div>
        </div>

        {/* Deductions */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6 print:border-gray-300">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <TrendingDown className="w-5 h-5 text-red-400" />
            Deductions
          </h2>
          <div className="space-y-3">
            {deductions.length === 0 ? (
              <p className="text-slate-muted text-sm">No deductions recorded</p>
            ) : (
              deductions.map((d, idx) => (
                <div key={idx} className="flex items-center justify-between py-2 border-b border-slate-border last:border-0">
                  <div>
                    <p className="text-foreground font-medium">{d.salary_component}</p>
                    {d.abbr && <p className="text-xs text-slate-muted">{d.abbr}</p>}
                  </div>
                  <p className="text-red-400 font-semibold">
                    -{formatCurrency(d.amount || d.default_amount || 0, currency)}
                  </p>
                </div>
              ))
            )}
            <div className="flex items-center justify-between pt-3 border-t border-slate-border">
              <p className="text-foreground font-semibold">Total Deductions</p>
              <p className="text-red-400 font-bold text-lg">
                -{formatCurrency(totalDeductions || slip.total_deduction || 0, currency)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="bg-gradient-to-r from-slate-card to-slate-elevated border border-slate-border rounded-xl p-6 print:border-gray-300">
        <div className="grid grid-cols-3 gap-6">
          <div className="text-center">
            <p className="text-slate-muted text-sm mb-1">Gross Pay</p>
            <p className="text-2xl font-bold text-foreground">
              {formatCurrency(slip.gross_pay || 0, currency)}
            </p>
          </div>
          <div className="text-center">
            <p className="text-slate-muted text-sm mb-1">Total Deductions</p>
            <p className="text-2xl font-bold text-red-400">
              -{formatCurrency(slip.total_deduction || 0, currency)}
            </p>
          </div>
          <div className="text-center">
            <p className="text-slate-muted text-sm mb-1">Net Pay</p>
            <div className="flex items-center justify-center gap-2">
              <Wallet2 className="w-6 h-6 text-green-400" />
              <p className="text-3xl font-bold text-green-400">
                {formatCurrency(slip.net_pay || 0, currency)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Payment Info (if paid) */}
      {isPaid && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 flex items-center gap-3">
          <CheckCircle2 className="w-6 h-6 text-green-400" />
          <div>
            <p className="text-green-400 font-semibold">Payment Completed</p>
            <p className="text-green-400/70 text-sm">
              This salary slip has been marked as paid.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
