'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrLeaveTypes,
  useHrHolidayLists,
  useHrLeavePolicies,
  useHrLeaveAllocations,
  useHrLeaveApplications,
} from '@/hooks/useApi';
import { cn, formatDate } from '@/lib/utils';
import { CalendarClock, FileSpreadsheet, Layers, ShieldCheck, Users } from 'lucide-react';

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

export default function HrLeavePage() {
  const [company, setCompany] = useState('');
  const [allocationStatus, setAllocationStatus] = useState('');
  const [applicationStatus, setApplicationStatus] = useState('');
  const [allocLimit, setAllocLimit] = useState(20);
  const [allocOffset, setAllocOffset] = useState(0);
  const [appLimit, setAppLimit] = useState(20);
  const [appOffset, setAppOffset] = useState(0);
  const [leaveSearch, setLeaveSearch] = useState('');

  const { data: leaveTypes, isLoading: leaveTypesLoading } = useHrLeaveTypes({
    search: leaveSearch || undefined,
    limit: 100,
  });
  const { data: holidayLists, isLoading: holidayListsLoading } = useHrHolidayLists({
    company: company || undefined,
  });
  const { data: leavePolicies, isLoading: leavePoliciesLoading } = useHrLeavePolicies();
  const { data: leaveAllocations, isLoading: allocLoading } = useHrLeaveAllocations({
    status: allocationStatus || undefined,
    company: company || undefined,
    limit: allocLimit,
    offset: allocOffset,
  });
  const { data: leaveApplications, isLoading: appLoading } = useHrLeaveApplications({
    status: applicationStatus || undefined,
    company: company || undefined,
    limit: appLimit,
    offset: appOffset,
  });

  const leaveTypeList = extractList(leaveTypes);
  const holidayList = extractList(holidayLists);
  const leavePolicyList = extractList(leavePolicies);
  const allocationList = extractList(leaveAllocations);
  const applicationList = extractList(leaveApplications);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Leave Types" value={leaveTypeList.total} icon={Layers} tone="text-blue-300" />
        <StatCard label="Holiday Lists" value={holidayList.total} icon={CalendarClock} tone="text-amber-300" />
        <StatCard label="Leave Policies" value={leavePolicyList.total} icon={FileSpreadsheet} tone="text-teal-electric" />
        <StatCard label="Active Allocations" value={allocationList.total} icon={ShieldCheck} tone="text-green-300" />
      </div>

      <div className="flex flex-wrap gap-3 items-center">
        <input
          type="text"
          placeholder="Filter by company"
          value={company}
          onChange={(e) => {
            setCompany(e.target.value);
            setAllocOffset(0);
            setAppOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
        <input
          type="text"
          placeholder="Search leave types"
          value={leaveSearch}
          onChange={(e) => setLeaveSearch(e.target.value)}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
        <select
          value={allocationStatus}
          onChange={(e) => {
            setAllocationStatus(e.target.value);
            setAllocOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All Allocation Status</option>
          <option value="draft">Draft</option>
          <option value="open">Open</option>
          <option value="approved">Approved</option>
        </select>
        <select
          value={applicationStatus}
          onChange={(e) => {
            setApplicationStatus(e.target.value);
            setAppOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All Application Status</option>
          <option value="open">Open</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DataTable
          columns={[
            { key: 'leave_type', header: 'Leave Type', sortable: true, render: (item: any) => <span className="text-white">{item.leave_type || item.name}</span> },
            {
              key: 'is_lwp',
              header: 'Loss of Pay',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border', item.is_lwp ? 'border-red-400 text-red-300 bg-red-500/10' : 'border-green-400 text-green-300 bg-green-500/10')}>
                  {item.is_lwp ? 'Yes' : 'No'}
                </span>
              ),
            },
            {
              key: 'is_carry_forward',
              header: 'Carry Forward',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border', item.is_carry_forward ? 'border-blue-400 text-blue-300 bg-blue-500/10' : 'border-slate-border text-slate-muted')}>
                  {item.is_carry_forward ? 'Yes' : 'No'}
                </span>
              ),
            },
          ]}
          data={(leaveTypeList.items || []).map((item: any) => ({ ...item, id: item.id || item.leave_type }))}
          keyField="id"
          loading={leaveTypesLoading}
          emptyMessage="No leave types defined"
        />

        <DataTable
          columns={[
            { key: 'holiday_list_name', header: 'Holiday List', render: (item: any) => <span className="text-white">{item.holiday_list_name}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            {
              key: 'from_date',
              header: 'Period',
              render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.from_date)} – ${formatDate(item.to_date)}`}</span>,
            },
            {
              key: 'holidays',
              header: 'Holidays',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-white">{item.holidays?.length ?? 0}</span>,
            },
          ]}
          data={(holidayList.items || []).map((item: any) => ({ ...item, id: item.id || item.holiday_list_name }))}
          keyField="id"
          loading={holidayListsLoading}
          emptyMessage="No holiday lists"
        />
      </div>

      <DataTable
        columns={[
          { key: 'leave_policy_name', header: 'Policy', render: (item: any) => <span className="text-white">{item.leave_policy_name}</span> },
          { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
          {
            key: 'details',
            header: 'Leave Types',
            align: 'right' as const,
            render: (item: any) => <span className="font-mono text-white">{item.details?.length ?? 0}</span>,
          },
        ]}
        data={(leavePolicyList.items || []).map((item: any) => ({ ...item, id: item.id || item.leave_policy_name }))}
        keyField="id"
        loading={leavePoliciesLoading}
        emptyMessage="No leave policies"
      />

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Leave Allocations</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
            { key: 'leave_type', header: 'Type', render: (item: any) => <span className="text-slate-muted text-sm">{item.leave_type}</span> },
            { key: 'from_date', header: 'From', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.from_date)}</span> },
            { key: 'to_date', header: 'To', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.to_date)}</span> },
            {
              key: 'total_leaves_allocated',
              header: 'Allocated',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-white">{item.total_leaves_allocated ?? item.new_leaves_allocated ?? 0}</span>,
            },
            {
              key: 'unused_leaves',
              header: 'Unused',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-slate-muted">{item.unused_leaves ?? 0}</span>,
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
          data={(allocationList.items || []).map((item: any) => ({ ...item, id: item.id || item.employee }))}
          keyField="id"
          loading={allocLoading}
          emptyMessage="No leave allocations"
        />
        {allocationList.total > allocLimit && (
          <Pagination
            total={allocationList.total}
            limit={allocLimit}
            offset={allocOffset}
            onPageChange={setAllocOffset}
            onLimitChange={(val) => {
              setAllocLimit(val);
              setAllocOffset(0);
            }}
          />
        )}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Leave Applications</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
            { key: 'leave_type', header: 'Type', render: (item: any) => <span className="text-slate-muted text-sm">{item.leave_type}</span> },
            { key: 'from_date', header: 'From', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.from_date)}</span> },
            { key: 'to_date', header: 'To', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.to_date)}</span> },
            {
              key: 'total_leave_days',
              header: 'Days',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-white">{item.total_leave_days ?? 0}</span>,
            },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'approved' ? 'border-green-400 text-green-300 bg-green-500/10' : item.status === 'rejected' ? 'border-red-400 text-red-300 bg-red-500/10' : 'border-amber-400 text-amber-300 bg-amber-500/10')}>
                  {item.status || 'open'}
                </span>
              ),
            },
          ]}
          data={(applicationList.items || []).map((item: any) => ({ ...item, id: item.id || `${item.employee}-${item.from_date}` }))}
          keyField="id"
          loading={appLoading}
          emptyMessage="No leave applications"
        />
        {applicationList.total > appLimit && (
          <Pagination
            total={applicationList.total}
            limit={appLimit}
            offset={appOffset}
            onPageChange={setAppOffset}
            onLimitChange={(val) => {
              setAppLimit(val);
              setAppOffset(0);
            }}
          />
        )}
      </div>
    </div>
  );
}
