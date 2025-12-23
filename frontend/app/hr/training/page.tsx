'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrTrainingPrograms,
  useHrTrainingEvents,
  useHrTrainingResults,
  useHrTrainingEventMutations,
  useHrTrainingResultMutations,
  useEmployees,
} from '@/hooks/useApi';
import { cn, formatDate, formatDateTime } from '@/lib/utils';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { GraduationCap, MapPin, Users, CheckCircle2, XCircle, Clock, AlertCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Button, FilterCard, FilterSelect, StatusPill } from '@/components/ui';
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

function StatusBadge({ status, type = 'event' }: { status: string; type?: 'event' | 'result' }) {
  const normalizedStatus = (status || '').toLowerCase();

  if (type === 'result') {
    const resultConfig: Record<string, { tone: StatusTone; icon: LucideIcon; label?: string }> = {
      passed: { tone: 'success', icon: CheckCircle2 },
      failed: { tone: 'danger', icon: XCircle },
      'in-progress': { tone: 'warning', icon: Clock, label: 'In progress' },
    };
    const config = resultConfig[normalizedStatus] || { tone: 'default', icon: AlertCircle };
    return (
      <StatusPill
        label={config.label || formatStatusLabel(status || 'unknown')}
        tone={config.tone}
        icon={config.icon}
        className="border border-current/30"
      />
    );
  }

  // Event status
  const eventConfig: Record<string, { tone: StatusTone; icon: LucideIcon; label?: string }> = {
    scheduled: { tone: 'warning', icon: Clock },
    completed: { tone: 'success', icon: CheckCircle2 },
    cancelled: { tone: 'danger', icon: XCircle },
  };
  const config = eventConfig[normalizedStatus] || eventConfig.scheduled;
  return (
    <StatusPill
      label={config.label || formatStatusLabel(status || 'scheduled')}
      tone={config.tone}
      icon={config.icon}
      className="border border-current/30"
    />
  );
}

const SINGLE_COMPANY = '';

export default function HrTrainingPage() {
  const [status, setStatus] = useState('scheduled');
  const [eventLimit, setEventLimit] = useState(20);
  const [eventOffset, setEventOffset] = useState(0);
  const [resultLimit, setResultLimit] = useState(20);
  const [resultOffset, setResultOffset] = useState(0);
  const [enrollEventId, setEnrollEventId] = useState('');
  const [enrollEmployeeIds, setEnrollEmployeeIds] = useState<string[]>([]);
  const [completeEventId, setCompleteEventId] = useState('');
  const [resultForm, setResultForm] = useState({
    employeeId: '',
    trainingEventId: '',
    result: 'passed',
    score: '',
  });
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: programs, isLoading: programsLoading } = useHrTrainingPrograms();
  const { data: events, isLoading: eventsLoading } = useHrTrainingEvents({
    status: status || undefined,
    company: SINGLE_COMPANY || undefined,
    limit: eventLimit,
    offset: eventOffset,
  });
  const { data: results, isLoading: resultsLoading } = useHrTrainingResults({
    limit: resultLimit,
    offset: resultOffset,
    employee_id: undefined,
  });
  const { data: employeesData } = useEmployees({ limit: 500 });
  const employees = { data: employeesData?.items || [], total: employeesData?.total ?? 0 };
  const eventMutations = useHrTrainingEventMutations();
  const resultMutations = useHrTrainingResultMutations();

  const programList = extractList(programs);
  const eventList = extractList(events);
  const resultList = extractList(results);
  const employeeList = extractList(employees);

  const handleEnroll = async () => {
    setActionError(null);
    if (!enrollEventId || !enrollEmployeeIds.length) {
      setActionError('Please select an event and at least one participant.');
      return;
    }
    try {
      await eventMutations.enroll(enrollEventId, enrollEmployeeIds);
      setEnrollEmployeeIds([]);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to enroll');
    }
  };

  const handleComplete = async () => {
    setActionError(null);
    if (!completeEventId) {
      setActionError('Please select an event to mark as complete.');
      return;
    }
    try {
      await eventMutations.complete(completeEventId);
      setCompleteEventId('');
    } catch (err: any) {
      setActionError(err?.message || 'Failed to complete event');
    }
  };

  const handleCreateResult = async () => {
    setActionError(null);
    if (!resultForm.employeeId || !resultForm.trainingEventId) {
      setActionError('Please select an employee and training event.');
      return;
    }
    const selectedEmployee = (employeeList.items || []).find((e: any) => (e.id || e.employee_id) === resultForm.employeeId);
    const selectedEvent = (eventList.items || []).find((e: any) => (e.id || e.name) === resultForm.trainingEventId);
    try {
      await resultMutations.create({
        employee: selectedEmployee?.name || selectedEmployee?.employee_name || resultForm.employeeId,
        employee_id: resultForm.employeeId ? Number(resultForm.employeeId) : undefined,
        employee_name: selectedEmployee?.employee_name || selectedEmployee?.name || '',
        training_event: selectedEvent?.training_event_name || resultForm.trainingEventId,
        result: resultForm.result || undefined,
        score: resultForm.score ? Number(resultForm.score) : undefined,
        company: selectedEmployee?.company || SINGLE_COMPANY || undefined,
      });
      setResultForm({
        employeeId: '',
        trainingEventId: '',
        result: 'passed',
        score: '',
      });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to record result');
    }
  };

  const toggleEmployeeEnroll = (empId: string) => {
    setEnrollEmployeeIds((prev) =>
      prev.includes(empId) ? prev.filter((id) => id !== empId) : [...prev, empId]
    );
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard title="Training Programs" value={programList.total} icon={GraduationCap} colorClass="text-amber-400" />
        <StatCard title="Events" value={eventList.total} icon={MapPin} colorClass="text-violet-400" />
        <StatCard title="Results" value={resultList.total} icon={Users} colorClass="text-emerald-400" />
      </div>

      {/* Filters */}
      <FilterCard title="Filter Events" contentClassName="flex flex-wrap gap-3 items-end" iconClassName="text-amber-400">
        <div>
          <FormLabel>Status</FormLabel>
          <FilterSelect
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setEventOffset(0);
            }}
          >
            <option value="">All statuses</option>
            <option value="scheduled">Scheduled</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </FilterSelect>
        </div>
      </FilterCard>

      {/* Action Forms */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Enroll Participants */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          <p className="text-foreground font-semibold">Enroll Participants</p>
          <div>
            <FormLabel required>Training Event</FormLabel>
            <select
              value={enrollEventId}
              onChange={(e) => setEnrollEventId(e.target.value)}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            >
              <option value="">Select event...</option>
              {(eventList.items || []).filter((e: any) => e.status !== 'completed' && e.status !== 'cancelled').map((event: any) => (
                <option key={event.id || event.training_event_name} value={event.id || event.training_event_name}>
                  {event.training_event_name} ({event.training_program})
                </option>
              ))}
            </select>
          </div>
          <div>
            <FormLabel required>Select Participants</FormLabel>
            <div className="bg-slate-elevated border border-slate-border rounded-lg p-2 max-h-32 overflow-y-auto space-y-1">
              {(employeeList.items || []).length === 0 && (
                <p className="text-slate-muted text-xs p-2">No employees found</p>
              )}
              {(employeeList.items || []).map((emp: any) => {
                const empId = String(emp.id || emp.employee_id || emp.name);
                const isSelected = enrollEmployeeIds.includes(empId);
                return (
                  <label
                    key={empId}
                    className={cn(
                      'flex items-center gap-2 p-1.5 rounded cursor-pointer text-sm',
                      isSelected ? 'bg-amber-500/20 text-amber-300' : 'text-slate-muted hover:bg-slate-border/30'
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleEmployeeEnroll(empId)}
                      className="rounded border-slate-border"
                    />
                    {emp.employee_name || emp.name || emp.email_id}
                  </label>
                );
              })}
            </div>
            {enrollEmployeeIds.length > 0 && (
              <p className="text-xs text-amber-400 mt-1">{enrollEmployeeIds.length} participant(s) selected</p>
            )}
          </div>
          <Button
            onClick={handleEnroll}
            disabled={!enrollEventId || !enrollEmployeeIds.length}
            className="bg-amber-500 text-slate-deep px-4 py-2 rounded-lg text-sm font-semibold hover:bg-amber-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Enroll Selected
          </Button>

          {/* Mark Complete Section */}
          <div className="pt-3 border-t border-slate-border space-y-3">
            <p className="text-foreground font-medium text-sm">Mark Event Complete</p>
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <FormLabel required>Select Event</FormLabel>
                <select
                  value={completeEventId}
                  onChange={(e) => setCompleteEventId(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                >
                  <option value="">Select event...</option>
                  {(eventList.items || []).filter((e: any) => e.status === 'scheduled').map((event: any) => (
                    <option key={event.id || event.training_event_name} value={event.id || event.training_event_name}>
                      {event.training_event_name}
                    </option>
                  ))}
                </select>
              </div>
              <Button
                onClick={handleComplete}
                disabled={!completeEventId}
                className="px-4 py-2 rounded-lg text-sm font-semibold border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Complete
              </Button>
            </div>
          </div>
        </div>

        {/* Record Training Result */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
          <p className="text-foreground font-semibold">Record Training Result</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <FormLabel required>Employee</FormLabel>
              <select
                value={resultForm.employeeId}
                onChange={(e) => setResultForm({ ...resultForm, employeeId: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              >
                <option value="">Select employee...</option>
                {(employeeList.items || []).map((emp: any) => (
                  <option key={emp.id || emp.employee_id} value={emp.id || emp.employee_id}>
                    {emp.employee_name || emp.name || emp.email_id}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <FormLabel required>Training Event</FormLabel>
              <select
                value={resultForm.trainingEventId}
                onChange={(e) => setResultForm({ ...resultForm, trainingEventId: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              >
                <option value="">Select event...</option>
                {(eventList.items || []).map((event: any) => (
                  <option key={event.id || event.training_event_name} value={event.id || event.training_event_name}>
                    {event.training_event_name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <FormLabel required>Result</FormLabel>
              <select
                value={resultForm.result}
                onChange={(e) => setResultForm({ ...resultForm, result: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              >
                <option value="passed">Passed</option>
                <option value="failed">Failed</option>
                <option value="in-progress">In Progress</option>
              </select>
            </div>
            <div>
              <FormLabel>Score (Optional)</FormLabel>
              <input
                type="number"
                placeholder="0-100"
                min="0"
                max="100"
                value={resultForm.score}
                onChange={(e) => setResultForm({ ...resultForm, score: e.target.value })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              />
            </div>
          </div>
          <Button
            onClick={handleCreateResult}
            disabled={!resultForm.employeeId || !resultForm.trainingEventId}
            className="bg-amber-500 text-slate-deep px-4 py-2 rounded-lg text-sm font-semibold hover:bg-amber-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Save Result
          </Button>
        </div>
      </div>
      {actionError && (
        <div className="bg-rose-500/10 border border-rose-500/40 rounded-lg p-3">
          <p className="text-rose-300 text-sm">{actionError}</p>
        </div>
      )}

      {/* Training Programs */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <GraduationCap className="w-4 h-4 text-amber-400" />
          <h3 className="text-foreground font-semibold">Training Programs</h3>
        </div>
        <DataTable
          columns={[
            { key: 'program_name', header: 'Program Name', render: (item: any) => <span className="text-foreground font-medium">{item.program_name}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            { key: 'description', header: 'Description', render: (item: any) => <span className="text-slate-muted text-sm truncate max-w-[200px] block">{item.description || '—'}</span> },
          ]}
          data={(programList.items || []).map((item: any) => ({ ...item, id: item.id || item.program_name }))}
          keyField="id"
          loading={programsLoading}
          emptyMessage="No training programs"
        />
      </div>

      {/* Training Events */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <MapPin className="w-4 h-4 text-violet-400" />
          <h3 className="text-foreground font-semibold">Training Events</h3>
        </div>
        <DataTable
          columns={[
            { key: 'training_event_name', header: 'Event Name', render: (item: any) => <span className="text-foreground font-medium">{item.training_event_name}</span> },
            { key: 'training_program', header: 'Program', render: (item: any) => <span className="text-slate-muted text-sm">{item.training_program}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            {
              key: 'start_time',
              header: 'Start Date',
              render: (item: any) => <span className="text-slate-muted text-sm">{formatDateTime(item.start_time)}</span>,
            },
            {
              key: 'end_time',
              header: 'End Date',
              render: (item: any) => <span className="text-slate-muted text-sm">{formatDateTime(item.end_time)}</span>,
            },
            {
              key: 'employees',
              header: 'Participants',
              align: 'right' as const,
              render: (item: any) => (
                <span className="inline-flex items-center gap-1 text-foreground">
                  <Users className="w-3 h-3 text-slate-muted" />
                  {item.employees?.length ?? 0}
                </span>
              ),
            },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => <StatusBadge status={item.status} type="event" />,
            },
          ]}
          data={(eventList.items || []).map((item: any) => ({ ...item, id: item.id || item.training_event_name }))}
          keyField="id"
          loading={eventsLoading}
          emptyMessage="No training events"
        />
        {eventList.total > eventLimit && (
          <Pagination
            total={eventList.total}
            limit={eventLimit}
            offset={eventOffset}
            onPageChange={setEventOffset}
            onLimitChange={(val) => {
              setEventLimit(val);
              setEventOffset(0);
            }}
          />
        )}
      </div>

      {/* Training Results */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <h3 className="text-foreground font-semibold">Training Results</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee Name', render: (item: any) => <span className="text-foreground font-medium">{item.employee_name || item.employee}</span> },
            { key: 'training_event', header: 'Training Event', render: (item: any) => <span className="text-slate-muted text-sm">{item.training_event}</span> },
            { key: 'result', header: 'Result', render: (item: any) => <StatusBadge status={item.result} type="result" /> },
            {
              key: 'score',
              header: 'Score',
              align: 'right' as const,
              render: (item: any) => (
                <span className={cn(
                  'font-mono',
                  item.score != null
                    ? item.score >= 70 ? 'text-emerald-300' : item.score >= 50 ? 'text-amber-300' : 'text-rose-300'
                    : 'text-slate-muted'
                )}>
                  {item.score != null ? `${item.score}%` : '—'}
                </span>
              ),
            },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
          ]}
          data={(resultList.items || []).map((item: any) => ({ ...item, id: item.id || `${item.employee}-${item.training_event}` }))}
          keyField="id"
          loading={resultsLoading}
          emptyMessage="No training results"
        />
        {resultList.total > resultLimit && (
          <Pagination
            total={resultList.total}
            limit={resultLimit}
            offset={resultOffset}
            onPageChange={setResultOffset}
            onLimitChange={(val) => {
              setResultLimit(val);
              setResultOffset(0);
            }}
          />
        )}
      </div>
    </div>
  );
}
