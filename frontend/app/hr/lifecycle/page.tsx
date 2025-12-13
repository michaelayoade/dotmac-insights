'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrEmployeeOnboardings,
  useHrEmployeeSeparations,
  useHrEmployeePromotions,
  useHrEmployeeTransfers,
} from '@/hooks/useApi';
import { cn, formatDate } from '@/lib/utils';
import { ArrowRightLeft, Flag, Rocket, UserCheck } from 'lucide-react';

function extractList<T>(response: any) {
  const items = response?.data || [];
  const total = response?.total ?? items.length;
  return { items, total };
}

function StatCard({
  label,
  value,
  icon: Icon,
  tone = 'text-teal-electric',
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  tone?: string;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between">
      <div>
        <p className="text-slate-muted text-sm">{label}</p>
        <p className="text-2xl font-bold text-white">{value}</p>
      </div>
      <div className="p-2 rounded-lg bg-slate-elevated">
        <Icon className={cn('w-5 h-5', tone)} />
      </div>
    </div>
  );
}

export default function HrLifecyclePage() {
  const [company, setCompany] = useState('');
  const [onboardingLimit, setOnboardingLimit] = useState(20);
  const [onboardingOffset, setOnboardingOffset] = useState(0);
  const [separationLimit, setSeparationLimit] = useState(20);
  const [separationOffset, setSeparationOffset] = useState(0);

  const { data: onboardings, isLoading: onboardingsLoading } = useHrEmployeeOnboardings({
    company: company || undefined,
    limit: onboardingLimit,
    offset: onboardingOffset,
  });
  const { data: separations, isLoading: separationsLoading } = useHrEmployeeSeparations({
    company: company || undefined,
    limit: separationLimit,
    offset: separationOffset,
  });
  const { data: promotions, isLoading: promotionsLoading } = useHrEmployeePromotions({ company: company || undefined });
  const { data: transfers, isLoading: transfersLoading } = useHrEmployeeTransfers({ company: company || undefined });

  const onboardingList = extractList(onboardings);
  const separationList = extractList(separations);
  const promotionList = extractList(promotions);
  const transferList = extractList(transfers);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Onboardings" value={onboardingList.total} icon={UserCheck} tone="text-teal-electric" />
        <StatCard label="Separations" value={separationList.total} icon={Flag} tone="text-amber-300" />
        <StatCard label="Promotions" value={promotionList.total} icon={Rocket} tone="text-green-300" />
        <StatCard label="Transfers" value={transferList.total} icon={ArrowRightLeft} tone="text-purple-300" />
      </div>

      <div className="flex flex-wrap gap-3 items-center">
        <input
          type="text"
          placeholder="Company"
          value={company}
          onChange={(e) => {
            setCompany(e.target.value);
            setOnboardingOffset(0);
            setSeparationOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <UserCheck className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Employee Onboardings</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            { key: 'status', header: 'Status', render: (item: any) => <span className="text-slate-muted text-sm capitalize">{item.status || 'open'}</span> },
            {
              key: 'activities',
              header: 'Activities',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-white">{item.activities?.length ?? 0}</span>,
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

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Flag className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Employee Separations</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            { key: 'reason', header: 'Reason', render: (item: any) => <span className="text-slate-muted text-sm">{item.reason || '—'}</span> },
            { key: 'notice_date', header: 'Notice', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.notice_date)}</span> },
            { key: 'relieving_date', header: 'Relieving', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.relieving_date)}</span> },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'closed' ? 'border-green-400 text-green-300 bg-green-500/10' : 'border-amber-400 text-amber-300 bg-amber-500/10')}>
                  {item.status || 'open'}
                </span>
              ),
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Rocket className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Promotions</h3>
          </div>
          <DataTable
            columns={[
              { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
              { key: 'promotion_date', header: 'Date', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.promotion_date)}</span> },
              {
                key: 'details',
                header: 'Details',
                render: (item: any) => (
                  <span className="text-slate-muted text-sm">
                    {item.details?.[0]?.current_designation || '—'} ➜ {item.details?.[0]?.new_designation || '—'}
                  </span>
                ),
              },
              {
                key: 'status',
                header: 'Status',
                render: (item: any) => (
                  <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'approved' ? 'border-green-400 text-green-300 bg-green-500/10' : 'border-amber-400 text-amber-300 bg-amber-500/10')}>
                    {item.status || 'draft'}
                  </span>
                ),
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
            <ArrowRightLeft className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Transfers</h3>
          </div>
          <DataTable
            columns={[
              { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
              { key: 'transfer_date', header: 'Date', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.transfer_date)}</span> },
              {
                key: 'details',
                header: 'Departments',
                render: (item: any) => (
                  <span className="text-slate-muted text-sm">
                    {item.details?.[0]?.from_department || '—'} ➜ {item.details?.[0]?.to_department || '—'}
                  </span>
                ),
              },
              {
                key: 'status',
                header: 'Status',
                render: (item: any) => (
                  <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'approved' ? 'border-green-400 text-green-300 bg-green-500/10' : 'border-amber-400 text-amber-300 bg-amber-500/10')}>
                    {item.status || 'draft'}
                  </span>
                ),
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
