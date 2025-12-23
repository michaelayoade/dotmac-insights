'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrShiftTypes,
  useHrShiftAssignments,
  useHrAttendances,
  useHrAttendanceRequests,
  useHrAttendanceMutations,
  useHrAttendanceRequestMutations,
} from '@/hooks/useApi';
import { cn, formatDate, formatDateTime } from '@/lib/utils';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { CalendarClock, Clock3, Layers, Users, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Button, StatusPill } from '@/components/ui';
import { StatCard } from '@/components/StatCard';

function extractList<T>(response: any) {
  const items = response?.data || [];
  const total = response?.total ?? items.length;
  return { items, total };
}

function StatusBadge({ status, type = 'attendance' }: { status: string; type?: 'attendance' | 'request' | 'shift' }) {
  const statusLower = status?.toLowerCase() || '';

  const configs: Record<string, Record<string, { tone: StatusTone; icon: LucideIcon; label?: string }>> = {
    attendance: {
      present: { tone: 'success', icon: CheckCircle2 },
      absent: { tone: 'danger', icon: XCircle },
      late: { tone: 'warning', icon: AlertCircle },
      'half day': { tone: 'info', icon: Clock3, label: 'Half day' },
    },
    request: {
      approved: { tone: 'success', icon: CheckCircle2 },
      rejected: { tone: 'danger', icon: XCircle },
      open: { tone: 'warning', icon: Clock3 },
      pending: { tone: 'warning', icon: Clock3 },
    },
    shift: {
      active: { tone: 'success', icon: CheckCircle2 },
      inactive: { tone: 'default', icon: XCircle },
    },
  };

  const config = configs[type]?.[statusLower] || { tone: 'default', icon: Clock3 };
  return (
    <StatusPill
      label={config.label || formatStatusLabel(status || 'unknown')}
      tone={config.tone}
      icon={config.icon}
      className="border border-current/30"
    />
  );
}

function FormLabel({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block text-xs text-slate-muted mb-1">
      {children}
      {required && <span className="text-rose-400 ml-0.5">*</span>}
    </label>
  );
}

const SINGLE_COMPANY = '';

export default function HrAttendancePage() {
  const [employeeId, setEmployeeId] = useState('');
  const [attendanceStatus, setAttendanceStatus] = useState('');
  const [attendanceDate, setAttendanceDate] = useState('');
  const [attLimit, setAttLimit] = useState(20);
  const [attOffset, setAttOffset] = useState(0);
  const [assignLimit, setAssignLimit] = useState(20);
  const [assignOffset, setAssignOffset] = useState(0);
  const [requestLimit, setRequestLimit] = useState(20);
  const [requestOffset, setRequestOffset] = useState(0);
  const [attendanceForm, setAttendanceForm] = useState({
    employee: '',
    employee_id: '',
    employee_name: '',
    attendance_date: '',
    status: 'present',
    in_time: '',
    out_time: '',
    working_hours: '',
    company: '',
    device_info: '',
    check_in_latitude: '',
    check_in_longitude: '',
    check_out_latitude: '',
    check_out_longitude: '',
  });
  const [bulkMarkIds, setBulkMarkIds] = useState('');
  const [bulkMarkDate, setBulkMarkDate] = useState('');
  const [bulkMarkStatus, setBulkMarkStatus] = useState('present');
  const [requestBulkIds, setRequestBulkIds] = useState('');
  const [requestBulkAction, setRequestBulkAction] = useState<'approve' | 'reject'>('approve');
  const [checkPayload, setCheckPayload] = useState({ latitude: '', longitude: '', device_info: '' });
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: shiftTypes, isLoading: shiftTypesLoading } = useHrShiftTypes({ company: SINGLE_COMPANY || undefined });
  const { data: shiftAssignments, isLoading: shiftAssignmentsLoading } = useHrShiftAssignments({
    employee_id: employeeId ? Number(employeeId) : undefined,
    limit: assignLimit,
    offset: assignOffset,
  });
  const { data: attendances, isLoading: attendancesLoading } = useHrAttendances({
    employee_id: employeeId ? Number(employeeId) : undefined,
    status: attendanceStatus || undefined,
    attendance_date: attendanceDate || undefined,
    company: SINGLE_COMPANY || undefined,
    limit: attLimit,
    offset: attOffset,
  });
  const { data: attendanceRequests, isLoading: attendanceRequestsLoading } = useHrAttendanceRequests({
    employee_id: employeeId ? Number(employeeId) : undefined,
    status: attendanceStatus || undefined,
    from_date: attendanceDate || undefined,
    to_date: attendanceDate || undefined,
    company: SINGLE_COMPANY || undefined,
    limit: requestLimit,
    offset: requestOffset,
  });
  const attendanceMutations = useHrAttendanceMutations();
  const attendanceRequestMutations = useHrAttendanceRequestMutations();

  const shiftTypeList = extractList(shiftTypes);
  const shiftAssignmentList = extractList(shiftAssignments);
  const attendanceList = extractList(attendances);
  const attendanceRequestList = extractList(attendanceRequests);

  const handleCreateAttendance = async () => {
    setActionError(null);
    if (!attendanceForm.employee || !attendanceForm.attendance_date || !attendanceForm.status) {
      setActionError('Employee, date, and status are required.');
      return;
    }
    try {
      await attendanceMutations.create({
        employee: attendanceForm.employee,
        employee_id: attendanceForm.employee_id ? Number(attendanceForm.employee_id) : undefined,
        employee_name: attendanceForm.employee_name || attendanceForm.employee,
        attendance_date: attendanceForm.attendance_date,
        status: attendanceForm.status,
        company: attendanceForm.company || SINGLE_COMPANY || undefined,
        in_time: attendanceForm.in_time || undefined,
        out_time: attendanceForm.out_time || undefined,
        working_hours: attendanceForm.working_hours ? Number(attendanceForm.working_hours) : undefined,
        check_in_latitude: attendanceForm.check_in_latitude ? Number(attendanceForm.check_in_latitude) : undefined,
        check_in_longitude: attendanceForm.check_in_longitude ? Number(attendanceForm.check_in_longitude) : undefined,
        check_out_latitude: attendanceForm.check_out_latitude ? Number(attendanceForm.check_out_latitude) : undefined,
        check_out_longitude: attendanceForm.check_out_longitude ? Number(attendanceForm.check_out_longitude) : undefined,
        device_info: attendanceForm.device_info || undefined,
        late_entry: false,
        early_exit: false,
        docstatus: 0,
      });
      setAttendanceForm({
        employee: '',
        employee_id: '',
        employee_name: '',
        attendance_date: '',
        status: 'present',
        in_time: '',
        out_time: '',
        working_hours: '',
        company: '',
        device_info: '',
        check_in_latitude: '',
        check_in_longitude: '',
        check_out_latitude: '',
        check_out_longitude: '',
      });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to record attendance');
    }
  };

  const handleBulkMark = async () => {
    setActionError(null);
    const ids = bulkMarkIds.split(',').map((s) => s.trim()).filter(Boolean);
    if (!ids.length || !bulkMarkDate || !bulkMarkStatus) {
      setActionError('Provide employee ids, date, and status.');
      return;
    }
    try {
      await attendanceMutations.bulkMark({
        employee_ids: ids,
        attendance_date: bulkMarkDate,
        status: bulkMarkStatus,
      });
      setBulkMarkIds('');
    } catch (err: any) {
      setActionError(err?.message || 'Bulk mark failed');
    }
  };

  const handleCheckIn = async (id: number | string) => {
    setActionError(null);
    try {
      await attendanceMutations.checkIn(id, {
        latitude: checkPayload.latitude ? Number(checkPayload.latitude) : undefined,
        longitude: checkPayload.longitude ? Number(checkPayload.longitude) : undefined,
        device_info: checkPayload.device_info || undefined,
      });
    } catch (err: any) {
      setActionError(err?.message || 'Check-in failed');
    }
  };

  const handleCheckOut = async (id: number | string) => {
    setActionError(null);
    try {
      await attendanceMutations.checkOut(id, {
        latitude: checkPayload.latitude ? Number(checkPayload.latitude) : undefined,
        longitude: checkPayload.longitude ? Number(checkPayload.longitude) : undefined,
      });
    } catch (err: any) {
      setActionError(err?.message || 'Check-out failed');
    }
  };

  const handleBulkRequestAction = async () => {
    setActionError(null);
    const ids = requestBulkIds.split(',').map((s) => s.trim()).filter(Boolean);
    if (!ids.length) {
      setActionError('Provide request ids.');
      return;
    }
    try {
      if (requestBulkAction === 'approve') {
        await attendanceRequestMutations.bulkApprove(ids);
      } else {
        await attendanceRequestMutations.bulkReject(ids);
      }
      setRequestBulkIds('');
    } catch (err: any) {
      setActionError(err?.message || 'Attendance request action failed');
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="Shift Types" value={shiftTypeList.total} icon={Layers} colorClass="text-blue-300" />
        <StatCard title="Assignments" value={shiftAssignmentList.total} icon={CalendarClock} colorClass="text-teal-electric" />
        <StatCard title="Attendance Records" value={attendanceList.total} icon={Clock3} colorClass="text-green-300" />
        <StatCard title="Attendance Requests" value={attendanceRequestList.total} icon={Users} colorClass="text-amber-300" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="space-y-3">
          <p className="text-foreground font-semibold">Record Attendance</p>
          <div>
            <FormLabel required>Employee Name</FormLabel>
            <input
              type="text"
              placeholder="e.g. John Smith"
              value={attendanceForm.employee_name || attendanceForm.employee}
              onChange={(e) => setAttendanceForm({ ...attendanceForm, employee: e.target.value, employee_name: e.target.value })}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <FormLabel required>Date</FormLabel>
              <input
                type="date"
                value={attendanceForm.attendance_date}
                onChange={(e) => setAttendanceForm({ ...attendanceForm, attendance_date: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <FormLabel required>Status</FormLabel>
              <select
                value={attendanceForm.status}
                onChange={(e) => setAttendanceForm({ ...attendanceForm, status: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              >
                <option value="present">Present</option>
                <option value="absent">Absent</option>
                <option value="late">Late</option>
                <option value="half day">Half Day</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <FormLabel>Check-in Time</FormLabel>
              <input
                type="datetime-local"
                value={attendanceForm.in_time}
                onChange={(e) => setAttendanceForm({ ...attendanceForm, in_time: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <FormLabel>Check-out Time</FormLabel>
              <input
                type="datetime-local"
                value={attendanceForm.out_time}
                onChange={(e) => setAttendanceForm({ ...attendanceForm, out_time: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
            </div>
          </div>
          <div>
            <FormLabel>Working Hours</FormLabel>
            <input
              type="number"
              step="0.5"
              placeholder="e.g. 8"
              value={attendanceForm.working_hours}
              onChange={(e) => setAttendanceForm({ ...attendanceForm, working_hours: e.target.value })}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
            />
          </div>
          <Button
            onClick={handleCreateAttendance}
            className="w-full bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
          >
            Save Attendance
          </Button>
        </div>

        <div className="space-y-3">
          <div className="space-y-2">
            <p className="text-foreground font-semibold">Bulk Mark Attendance</p>
            <input
              type="text"
              placeholder="Employee IDs (comma-separated)"
              value={bulkMarkIds}
              onChange={(e) => setBulkMarkIds(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                type="date"
                value={bulkMarkDate}
                onChange={(e) => setBulkMarkDate(e.target.value)}
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
              <select
                value={bulkMarkStatus}
                onChange={(e) => setBulkMarkStatus(e.target.value)}
                className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              >
                <option value="present">Present</option>
                <option value="absent">Absent</option>
                <option value="late">Late</option>
                <option value="open">Open</option>
              </select>
            </div>
            <Button
              onClick={handleBulkMark}
              className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
            >
              Apply Bulk Mark
            </Button>
          </div>
          <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 space-y-2">
            <p className="text-foreground font-semibold text-sm">Check-in/out defaults</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Latitude"
                value={checkPayload.latitude}
                onChange={(e) => setCheckPayload({ ...checkPayload, latitude: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
              <input
                type="text"
                placeholder="Longitude"
                value={checkPayload.longitude}
                onChange={(e) => setCheckPayload({ ...checkPayload, longitude: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
              />
            </div>
            <input
              type="text"
              placeholder="Device info"
              value={checkPayload.device_info}
              onChange={(e) => setCheckPayload({ ...checkPayload, device_info: e.target.value })}
              className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
            />
            <p className="text-slate-muted text-xs">Used when triggering check-in/out actions below.</p>
          </div>
        </div>
      </div>
      {actionError && <p className="text-red-400 text-sm">{actionError}</p>}

      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <p className="text-foreground font-semibold mb-3">Filters</p>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <FormLabel>Employee</FormLabel>
            <input
              type="text"
              placeholder="Search by name or ID"
              value={employeeId}
              onChange={(e) => {
                setEmployeeId(e.target.value);
                setAttOffset(0);
                setAssignOffset(0);
                setRequestOffset(0);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <div>
            <FormLabel>Date</FormLabel>
            <input
              type="date"
              value={attendanceDate}
              onChange={(e) => {
                setAttendanceDate(e.target.value);
                setAttOffset(0);
                setRequestOffset(0);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <div>
            <FormLabel>Status</FormLabel>
            <select
              value={attendanceStatus}
              onChange={(e) => {
                setAttendanceStatus(e.target.value);
                setAttOffset(0);
                setRequestOffset(0);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              <option value="">All Status</option>
              <option value="present">Present</option>
              <option value="absent">Absent</option>
              <option value="late">Late</option>
              <option value="half day">Half Day</option>
            </select>
          </div>
        </div>
      </div>

      <DataTable
        columns={[
          { key: 'shift_type', header: 'Shift Type', render: (item: any) => <span className="text-foreground">{item.shift_type || item.name}</span> },
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
          <h3 className="text-foreground font-semibold">Shift Assignments</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-foreground font-medium">{item.employee_name || item.employee}</span> },
            { key: 'shift_type', header: 'Shift', render: (item: any) => <span className="text-slate-muted text-sm">{item.shift_type}</span> },
            {
              key: 'from_date',
              header: 'Period',
              render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.from_date) || '—'} – ${formatDate(item.to_date) || '—'}`}</span>,
            },
            { key: 'status', header: 'Status', render: (item: any) => <StatusBadge status={item.status || 'active'} type="shift" /> },
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
          <h3 className="text-foreground font-semibold">Attendance</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-foreground font-medium">{item.employee_name || item.employee}</span> },
            { key: 'attendance_date', header: 'Date', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.attendance_date) || '—'}</span> },
            { key: 'status', header: 'Status', render: (item: any) => <StatusBadge status={item.status} type="attendance" /> },
            { key: 'in_time', header: 'Check-in', render: (item: any) => <span className="text-slate-muted text-sm">{formatDateTime(item.in_time) || '—'}</span> },
            { key: 'out_time', header: 'Check-out', render: (item: any) => <span className="text-slate-muted text-sm">{formatDateTime(item.out_time) || '—'}</span> },
            {
              key: 'working_hours',
              header: 'Hours Worked',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-foreground">{item.working_hours ? `${item.working_hours}h` : '—'}</span>,
            },
            {
              key: 'actions',
              header: 'Actions',
              render: (item: any) => (
                <div className="flex gap-2 text-xs">
                  <Button
                    onClick={(e) => { e.stopPropagation(); handleCheckIn(item.id || item.employee); }}
                    className="px-2 py-1 rounded border border-teal-electric text-teal-electric hover:bg-teal-electric/10"
                  >
                    Check-in
                  </Button>
                  <Button
                    onClick={(e) => { e.stopPropagation(); handleCheckOut(item.id || item.employee); }}
                    className="px-2 py-1 rounded border border-slate-border text-slate-muted hover:bg-slate-elevated/50"
                  >
                    Check-out
                  </Button>
                </div>
              ),
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
          <h3 className="text-foreground font-semibold">Attendance Requests</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-foreground font-medium">{item.employee_name || item.employee}</span> },
            {
              key: 'from_date',
              header: 'Request Period',
              render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.from_date) || '—'} – ${formatDate(item.to_date) || '—'}`}</span>,
            },
            {
              key: 'reason',
              header: 'Reason',
              render: (item: any) => <span className="text-slate-muted text-sm truncate max-w-[200px] block">{item.reason || '—'}</span>,
            },
            { key: 'status', header: 'Status', render: (item: any) => <StatusBadge status={item.status || 'open'} type="request" /> },
            {
              key: 'actions',
              header: 'Actions',
              render: (item: any) => (
                <div className="flex gap-2 text-xs">
                  <Button
                    onClick={(e) => { e.stopPropagation(); attendanceRequestMutations.approve(item.id); }}
                    className="px-2 py-1 rounded border border-emerald-500 text-emerald-300 hover:bg-emerald-500/10"
                  >
                    Approve
                  </Button>
                  <Button
                    onClick={(e) => { e.stopPropagation(); attendanceRequestMutations.reject(item.id); }}
                    className="px-2 py-1 rounded border border-rose-500 text-rose-300 hover:bg-rose-500/10"
                  >
                    Reject
                  </Button>
                </div>
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
        <div className="bg-slate-elevated border border-slate-border rounded-lg p-4 space-y-2">
          <p className="text-foreground font-semibold">Bulk Approve/Reject</p>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="text"
              placeholder="Request IDs (comma-separated)"
              value={requestBulkIds}
              onChange={(e) => setRequestBulkIds(e.target.value)}
              className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
            />
            <select
              value={requestBulkAction}
              onChange={(e) => setRequestBulkAction(e.target.value as 'approve' | 'reject')}
              className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground"
            >
              <option value="approve">Approve</option>
              <option value="reject">Reject</option>
            </select>
          </div>
          <Button
            onClick={handleBulkRequestAction}
            className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
          >
            Run Bulk Action
          </Button>
        </div>
      </div>
    </div>
  );
}
