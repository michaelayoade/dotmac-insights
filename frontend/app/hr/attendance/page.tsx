'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrShiftTypes,
  useHrShiftAssignments,
  useHrAttendances,
  useHrAttendanceRequests,
} from '@/hooks/useApi';
import { cn, formatDate, formatDateTime } from '@/lib/utils';
import { CalendarClock, Clock3, Layers, Users } from 'lucide-react';

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

export default function HrAttendancePage() {
  const [company, setCompany] = useState('');
  const [employeeId, setEmployeeId] = useState('');
  const [attendanceStatus, setAttendanceStatus] = useState('');
  const [attendanceDate, setAttendanceDate] = useState('');
  const [attLimit, setAttLimit] = useState(20);
  const [attOffset, setAttOffset] = useState(0);
  const [assignLimit, setAssignLimit] = useState(20);
  const [assignOffset, setAssignOffset] = useState(0);
  const [requestLimit, setRequestLimit] = useState(20);
  const [requestOffset, setRequestOffset] = useState(0);

  const { data: shiftTypes, isLoading: shiftTypesLoading } = useHrShiftTypes({ company: company || undefined });
  const { data: shiftAssignments, isLoading: shiftAssignmentsLoading } = useHrShiftAssignments({
    employee_id: employeeId ? Number(employeeId) : undefined,
    limit: assignLimit,
    offset: assignOffset,
  });
  const { data: attendances, isLoading: attendancesLoading } = useHrAttendances({
    employee_id: employeeId ? Number(employeeId) : undefined,
    status: attendanceStatus || undefined,
    attendance_date: attendanceDate || undefined,
    company: company || undefined,
    limit: attLimit,
    offset: attOffset,
  });
  const { data: attendanceRequests, isLoading: attendanceRequestsLoading } = useHrAttendanceRequests({
    employee_id: employeeId ? Number(employeeId) : undefined,
    status: attendanceStatus || undefined,
    from_date: attendanceDate || undefined,
    to_date: attendanceDate || undefined,
    company: company || undefined,
    limit: requestLimit,
    offset: requestOffset,
  });

  const shiftTypeList = extractList(shiftTypes);
  const shiftAssignmentList = extractList(shiftAssignments);
  const attendanceList = extractList(attendances);
  const attendanceRequestList = extractList(attendanceRequests);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Shift Types" value={shiftTypeList.total} icon={Layers} tone="text-blue-300" />
        <StatCard label="Assignments" value={shiftAssignmentList.total} icon={CalendarClock} tone="text-teal-electric" />
        <StatCard label="Attendance Records" value={attendanceList.total} icon={Clock3} tone="text-green-300" />
        <StatCard label="Attendance Requests" value={attendanceRequestList.total} icon={Users} tone="text-amber-300" />
      </div>

      <div className="flex flex-wrap gap-3 items-center">
        <input
          type="text"
          placeholder="Company"
          value={company}
          onChange={(e) => {
            setCompany(e.target.value);
            setAttOffset(0);
            setAssignOffset(0);
            setRequestOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
        <input
          type="number"
          placeholder="Employee ID"
          value={employeeId}
          onChange={(e) => {
            setEmployeeId(e.target.value);
            setAttOffset(0);
            setAssignOffset(0);
            setRequestOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
        <input
          type="date"
          value={attendanceDate}
          onChange={(e) => {
            setAttendanceDate(e.target.value);
            setAttOffset(0);
            setRequestOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
        <select
          value={attendanceStatus}
          onChange={(e) => {
            setAttendanceStatus(e.target.value);
            setAttOffset(0);
            setRequestOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All Status</option>
          <option value="present">Present</option>
          <option value="absent">Absent</option>
          <option value="late">Late</option>
          <option value="open">Open</option>
        </select>
      </div>

      <DataTable
        columns={[
          { key: 'shift_type', header: 'Shift Type', render: (item: any) => <span className="text-white">{item.shift_type || item.name}</span> },
          { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
        ]}
        data={(shiftTypeList.items || []).map((item: any) => ({ ...item, id: item.id || item.shift_type }))}
        keyField="id"
        loading={shiftTypesLoading}
        emptyMessage="No shift types defined"
      />

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <CalendarClock className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Shift Assignments</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
            { key: 'shift_type', header: 'Shift', render: (item: any) => <span className="text-slate-muted text-sm">{item.shift_type}</span> },
            {
              key: 'from_date',
              header: 'Period',
              render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.from_date)} – ${formatDate(item.to_date)}`}</span>,
            },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'active' ? 'border-green-400 text-green-300 bg-green-500/10' : 'border-amber-400 text-amber-300 bg-amber-500/10')}>
                  {item.status || 'active'}
                </span>
              ),
            },
          ]}
          data={(shiftAssignmentList.items || []).map((item: any) => ({ ...item, id: item.id || item.employee }))}
          keyField="id"
          loading={shiftAssignmentsLoading}
          emptyMessage="No shift assignments"
        />
        {shiftAssignmentList.total > assignLimit && (
          <Pagination
            total={shiftAssignmentList.total}
            limit={assignLimit}
            offset={assignOffset}
            onPageChange={setAssignOffset}
            onLimitChange={(val) => {
              setAssignLimit(val);
              setAssignOffset(0);
            }}
          />
        )}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Clock3 className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Attendance</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
            { key: 'attendance_date', header: 'Date', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.attendance_date)}</span> },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'present' ? 'border-green-400 text-green-300 bg-green-500/10' : item.status === 'absent' ? 'border-red-400 text-red-300 bg-red-500/10' : 'border-amber-400 text-amber-300 bg-amber-500/10')}>
                  {item.status}
                </span>
              ),
            },
            { key: 'in_time', header: 'In', render: (item: any) => <span className="text-slate-muted text-sm">{formatDateTime(item.in_time)}</span> },
            { key: 'out_time', header: 'Out', render: (item: any) => <span className="text-slate-muted text-sm">{formatDateTime(item.out_time)}</span> },
            {
              key: 'working_hours',
              header: 'Hours',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-white">{item.working_hours ?? '—'}</span>,
            },
          ]}
          data={(attendanceList.items || []).map((item: any) => ({ ...item, id: item.id || `${item.employee}-${item.attendance_date}` }))}
          keyField="id"
          loading={attendancesLoading}
          emptyMessage="No attendance records"
        />
        {attendanceList.total > attLimit && (
          <Pagination
            total={attendanceList.total}
            limit={attLimit}
            offset={attOffset}
            onPageChange={setAttOffset}
            onLimitChange={(val) => {
              setAttLimit(val);
              setAttOffset(0);
            }}
          />
        )}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Attendance Requests</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
            {
              key: 'from_date',
              header: 'Date(s)',
              render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.from_date)} – ${formatDate(item.to_date)}`}</span>,
            },
            {
              key: 'reason',
              header: 'Reason',
              render: (item: any) => <span className="text-slate-muted text-sm truncate max-w-[200px] block">{item.reason || '—'}</span>,
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
          data={(attendanceRequestList.items || []).map((item: any) => ({ ...item, id: item.id || `${item.employee}-${item.from_date}` }))}
          keyField="id"
          loading={attendanceRequestsLoading}
          emptyMessage="No attendance requests"
        />
        {attendanceRequestList.total > requestLimit && (
          <Pagination
            total={attendanceRequestList.total}
            limit={requestLimit}
            offset={requestOffset}
            onPageChange={setRequestOffset}
            onLimitChange={(val) => {
              setRequestLimit(val);
              setRequestOffset(0);
            }}
          />
        )}
      </div>
    </div>
  );
}
