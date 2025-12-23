'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrEmployeeOnboardings,
  useHrEmployeeSeparations,
  useHrEmployeePromotions,
  useHrEmployeeTransfers,
  useHrLifecycleMutations,
} from '@/hooks/useApi';
import { cn, formatDate } from '@/lib/utils';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { ArrowRightLeft, Flag, Rocket, UserCheck, CheckCircle2, Clock, XCircle, FileEdit, Send, AlertCircle, ArrowRight } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Button, StatusPill } from '@/components/ui';
import { StatCard } from '@/components/StatCard';

function extractList<T>(response: any) {
  const items = response?.data || [];
  const total = response?.total ?? items.length;
  return { items, total };
}

function FormLabel({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block text-xs text-slate-muted mb-1">
      {children}
      {required && <span className="text-rose-400 ml-0.5">*</span>}
    </label>
  );
}

function StatusBadge({ status, type = 'onboarding' }: { status: string; type?: 'onboarding' | 'separation' | 'promotion' | 'transfer' }) {
  const normalizedStatus = (status || '').toLowerCase();

  const configs: Record<string, Record<string, { tone: StatusTone; icon: LucideIcon; label?: string }>> = {
    onboarding: {
      open: { tone: 'warning', icon: Clock },
      in_progress: { tone: 'info', icon: ArrowRight, label: 'In progress' },
      completed: { tone: 'success', icon: CheckCircle2 },
      closed: { tone: 'default', icon: XCircle },
    },
    separation: {
      open: { tone: 'warning', icon: Clock },
      in_progress: { tone: 'danger', icon: ArrowRight, label: 'In progress' },
      closed: { tone: 'default', icon: CheckCircle2 },
    },
    promotion: {
      draft: { tone: 'default', icon: FileEdit },
      submitted: { tone: 'warning', icon: Send },
      approved: { tone: 'success', icon: CheckCircle2 },
      rejected: { tone: 'danger', icon: XCircle },
    },
    transfer: {
      draft: { tone: 'default', icon: FileEdit },
      submitted: { tone: 'warning', icon: Send },
      approved: { tone: 'success', icon: CheckCircle2 },
      rejected: { tone: 'danger', icon: XCircle },
    },
  };

  const typeConfig = configs[type] || configs.onboarding;
  const defaultKey = type === 'onboarding' || type === 'separation' ? 'open' : 'draft';
  const style = typeConfig[normalizedStatus] || typeConfig[defaultKey];

  return (
    <StatusPill
      label={style.label || formatStatusLabel(status || defaultKey)}
      tone={style.tone}
      icon={style.icon}
      className="border border-current/30"
    />
  );
}

const SINGLE_COMPANY = '';

export default function HrLifecyclePage() {
  const [onboardingLimit, setOnboardingLimit] = useState(20);
  const [onboardingOffset, setOnboardingOffset] = useState(0);
  const [separationLimit, setSeparationLimit] = useState(20);
  const [separationOffset, setSeparationOffset] = useState(0);
  const [statusForm, setStatusForm] = useState({
    onboardingId: '',
    onboardingStatus: 'open',
    separationId: '',
    separationStatus: 'open',
    promotionId: '',
    promotionStatus: 'draft',
    transferId: '',
    transferStatus: 'draft',
  });
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: onboardings, isLoading: onboardingsLoading } = useHrEmployeeOnboardings({
    company: SINGLE_COMPANY || undefined,
    limit: onboardingLimit,
    offset: onboardingOffset,
  });
  const { data: separations, isLoading: separationsLoading } = useHrEmployeeSeparations({
    company: SINGLE_COMPANY || undefined,
    limit: separationLimit,
    offset: separationOffset,
  });
  const { data: promotions, isLoading: promotionsLoading } = useHrEmployeePromotions({ company: SINGLE_COMPANY || undefined });
  const { data: transfers, isLoading: transfersLoading } = useHrEmployeeTransfers({ company: SINGLE_COMPANY || undefined });
  const lifecycleMutations = useHrLifecycleMutations();

  const onboardingList = extractList(onboardings);
  const separationList = extractList(separations);
  const promotionList = extractList(promotions);
  const transferList = extractList(transfers);

  const handleStatusUpdate = async (type: 'onboarding' | 'separation' | 'promotion' | 'transfer') => {
    setActionError(null);
    try {
      if (type === 'onboarding') {
        if (!statusForm.onboardingId) throw new Error('Onboarding ID required');
        await lifecycleMutations.updateOnboardingStatus(statusForm.onboardingId, statusForm.onboardingStatus);
      } else if (type === 'separation') {
        if (!statusForm.separationId) throw new Error('Separation ID required');
        await lifecycleMutations.updateSeparationStatus(statusForm.separationId, statusForm.separationStatus);
      } else if (type === 'promotion') {
        if (!statusForm.promotionId) throw new Error('Promotion ID required');
        await lifecycleMutations.updatePromotionStatus(statusForm.promotionId, statusForm.promotionStatus);
      } else {
        if (!statusForm.transferId) throw new Error('Transfer ID required');
        await lifecycleMutations.updateTransferStatus(statusForm.transferId, statusForm.transferStatus);
      }
    } catch (err: any) {
      setActionError(err?.message || 'Update failed');
    }
  };

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="Onboardings" value={onboardingList.total} icon={UserCheck} colorClass="text-emerald-400" />
        <StatCard title="Separations" value={separationList.total} icon={Flag} colorClass="text-rose-400" />
        <StatCard title="Promotions" value={promotionList.total} icon={Rocket} colorClass="text-amber-400" />
        <StatCard title="Transfers" value={transferList.total} icon={ArrowRightLeft} colorClass="text-violet-400" />
      </div>


      {/* Update Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Onboarding & Separation Updates */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          <p className="text-foreground font-semibold">Update Onboarding Status</p>
          <div className="space-y-3">
            <div>
              <FormLabel required>Select Employee</FormLabel>
              <select
                value={statusForm.onboardingId}
                onChange={(e) => setStatusForm({ ...statusForm, onboardingId: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              >
                <option value="">Select onboarding record...</option>
                {(onboardingList.items || []).map((item: any) => (
                  <option key={item.id || item.employee} value={item.id || item.employee}>
                    {item.employee_name || item.employee} ({item.status || 'open'})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <FormLabel required>New Status</FormLabel>
              <select
                value={statusForm.onboardingStatus}
                onChange={(e) => setStatusForm({ ...statusForm, onboardingStatus: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              >
                <option value="open">Open</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="closed">Closed</option>
              </select>
            </div>
            <Button
              onClick={() => handleStatusUpdate('onboarding')}
              disabled={!statusForm.onboardingId}
              className="bg-amber-500 text-slate-deep px-4 py-2 rounded-lg text-sm font-semibold hover:bg-amber-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Update Onboarding
            </Button>
          </div>

          <div className="pt-4 border-t border-slate-border space-y-3">
            <p className="text-foreground font-semibold">Update Separation Status</p>
            <div>
              <FormLabel required>Select Employee</FormLabel>
              <select
                value={statusForm.separationId}
                onChange={(e) => setStatusForm({ ...statusForm, separationId: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              >
                <option value="">Select separation record...</option>
                {(separationList.items || []).map((item: any) => (
                  <option key={item.id || item.employee} value={item.id || item.employee}>
                    {item.employee_name || item.employee} ({item.status || 'open'})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <FormLabel required>New Status</FormLabel>
              <select
                value={statusForm.separationStatus}
                onChange={(e) => setStatusForm({ ...statusForm, separationStatus: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              >
                <option value="open">Open</option>
                <option value="in_progress">In Progress</option>
                <option value="closed">Closed</option>
              </select>
            </div>
            <Button
              onClick={() => handleStatusUpdate('separation')}
              disabled={!statusForm.separationId}
              className="px-4 py-2 rounded-lg text-sm font-semibold border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Update Separation
            </Button>
          </div>
        </div>

        {/* Promotion & Transfer Updates */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          <p className="text-foreground font-semibold">Update Promotion Status</p>
          <div className="space-y-3">
            <div>
              <FormLabel required>Select Employee</FormLabel>
              <select
                value={statusForm.promotionId}
                onChange={(e) => setStatusForm({ ...statusForm, promotionId: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              >
                <option value="">Select promotion record...</option>
                {(promotionList.items || []).map((item: any) => (
                  <option key={item.id || item.employee} value={item.id || item.employee}>
                    {item.employee_name || item.employee} ({item.status || 'draft'})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <FormLabel required>New Status</FormLabel>
              <select
                value={statusForm.promotionStatus}
                onChange={(e) => setStatusForm({ ...statusForm, promotionStatus: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              >
                <option value="draft">Draft</option>
                <option value="submitted">Submitted</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>
            <Button
              onClick={() => handleStatusUpdate('promotion')}
              disabled={!statusForm.promotionId}
              className="bg-amber-500 text-slate-deep px-4 py-2 rounded-lg text-sm font-semibold hover:bg-amber-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Update Promotion
            </Button>
          </div>

          <div className="pt-4 border-t border-slate-border space-y-3">
            <p className="text-foreground font-semibold">Update Transfer Status</p>
            <div>
              <FormLabel required>Select Employee</FormLabel>
              <select
                value={statusForm.transferId}
                onChange={(e) => setStatusForm({ ...statusForm, transferId: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              >
                <option value="">Select transfer record...</option>
                {(transferList.items || []).map((item: any) => (
                  <option key={item.id || item.employee} value={item.id || item.employee}>
                    {item.employee_name || item.employee} ({item.status || 'draft'})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <FormLabel required>New Status</FormLabel>
              <select
                value={statusForm.transferStatus}
                onChange={(e) => setStatusForm({ ...statusForm, transferStatus: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              >
                <option value="draft">Draft</option>
                <option value="submitted">Submitted</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>
            <Button
              onClick={() => handleStatusUpdate('transfer')}
              disabled={!statusForm.transferId}
              className="px-4 py-2 rounded-lg text-sm font-semibold border border-violet-500/40 text-violet-300 hover:bg-violet-500/10 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Update Transfer
            </Button>
          </div>
        </div>
      </div>

      {actionError && (
        <div className="bg-rose-500/10 border border-rose-500/40 rounded-lg p-3">
          <p className="text-rose-300 text-sm">{actionError}</p>
        </div>
      )}


      {/* Onboardings Table */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <UserCheck className="w-4 h-4 text-emerald-400" />
          <h3 className="text-foreground font-semibold">Employee Onboardings</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee Name', render: (item: any) => <span className="text-foreground font-medium">{item.employee_name || item.employee}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            { key: 'status', header: 'Status', render: (item: any) => <StatusBadge status={item.status} type="onboarding" /> },
            {
              key: 'activities',
              header: 'Activities',
              align: 'right' as const,
              render: (item: any) => (
                <span className="inline-flex items-center gap-1 text-foreground">
                  <CheckCircle2 className="w-3 h-3 text-slate-muted" />
                  {item.activities?.length ?? 0}
                </span>
              ),
            },
          ]}
          data={(onboardingList.items || []).map((item: any) => ({ ...item, id: item.id || item.employee }))}
          keyField="id"
          loading={onboardingsLoading}
          emptyMessage="No onboarding records"
        />
        {onboardingList.total > onboardingLimit && (
          <Pagination
            total={onboardingList.total}
            limit={onboardingLimit}
            offset={onboardingOffset}
            onPageChange={setOnboardingOffset}
            onLimitChange={(val) => {
              setOnboardingLimit(val);
              setOnboardingOffset(0);
            }}
          />
        )}
      </div>

      {/* Separations Table */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Flag className="w-4 h-4 text-rose-400" />
          <h3 className="text-foreground font-semibold">Employee Separations</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee Name', render: (item: any) => <span className="text-foreground font-medium">{item.employee_name || item.employee}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            { key: 'reason', header: 'Reason', render: (item: any) => <span className="text-slate-muted text-sm">{item.reason || '—'}</span> },
            { key: 'notice_date', header: 'Notice Date', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.notice_date)}</span> },
            { key: 'relieving_date', header: 'Relieving Date', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.relieving_date)}</span> },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => <StatusBadge status={item.status} type="separation" />,
            },
          ]}
          data={(separationList.items || []).map((item: any) => ({ ...item, id: item.id || `${item.employee}-${item.notice_date}` }))}
          keyField="id"
          loading={separationsLoading}
          emptyMessage="No separations"
        />
        {separationList.total > separationLimit && (
          <Pagination
            total={separationList.total}
            limit={separationLimit}
            offset={separationOffset}
            onPageChange={setSeparationOffset}
            onLimitChange={(val) => {
              setSeparationLimit(val);
              setSeparationOffset(0);
            }}
          />
        )}
      </div>

      {/* Promotions & Transfers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Rocket className="w-4 h-4 text-amber-400" />
            <h3 className="text-foreground font-semibold">Promotions</h3>
          </div>
          <DataTable
            columns={[
              { key: 'employee', header: 'Employee Name', render: (item: any) => <span className="text-foreground font-medium">{item.employee_name || item.employee}</span> },
              { key: 'promotion_date', header: 'Date', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.promotion_date)}</span> },
              {
                key: 'details',
                header: 'Designation Change',
                render: (item: any) => (
                  <span className="text-slate-muted text-sm inline-flex items-center gap-1">
                    {item.details?.[0]?.current_designation || '—'}
                    <ArrowRight className="w-3 h-3 text-amber-400" />
                    {item.details?.[0]?.new_designation || '—'}
                  </span>
                ),
              },
              {
                key: 'status',
                header: 'Status',
                render: (item: any) => <StatusBadge status={item.status} type="promotion" />,
              },
            ]}
            data={(promotionList.items || []).map((item: any) => ({ ...item, id: item.id || item.employee }))}
            keyField="id"
            loading={promotionsLoading}
            emptyMessage="No promotions recorded"
          />
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <ArrowRightLeft className="w-4 h-4 text-violet-400" />
            <h3 className="text-foreground font-semibold">Transfers</h3>
          </div>
          <DataTable
            columns={[
              { key: 'employee', header: 'Employee Name', render: (item: any) => <span className="text-foreground font-medium">{item.employee_name || item.employee}</span> },
              { key: 'transfer_date', header: 'Date', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.transfer_date)}</span> },
              {
                key: 'details',
                header: 'Department Change',
                render: (item: any) => (
                  <span className="text-slate-muted text-sm inline-flex items-center gap-1">
                    {item.details?.[0]?.from_department || '—'}
                    <ArrowRight className="w-3 h-3 text-violet-400" />
                    {item.details?.[0]?.to_department || '—'}
                  </span>
                ),
              },
              {
                key: 'status',
                header: 'Status',
                render: (item: any) => <StatusBadge status={item.status} type="transfer" />,
              },
            ]}
            data={(transferList.items || []).map((item: any) => ({ ...item, id: item.id || item.employee }))}
            keyField="id"
            loading={transfersLoading}
            emptyMessage="No transfers recorded"
          />
        </div>
      </div>
    </div>
  );
}
