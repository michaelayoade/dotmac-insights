'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';
import { AlertTriangle, ArrowLeft, Clock, LifeBuoy, MessageSquare, ActivitySquare, Mail, Link2, Receipt, Send, Users, ShieldCheck } from 'lucide-react';
import {
  useSupportTicketDetail,
  useSupportTicketCommentMutations,
  useSupportTicketMutations,
  useSupportTicketActivityMutations,
  useSupportTicketCommunicationMutations,
  useSupportTicketDependencyMutations,
} from '@/hooks/useApi';

function formatDate(value?: string | null) {
  if (!value) return '-';
  const dt = new Date(value);
  return dt.toLocaleString('en-NG', { dateStyle: 'medium', timeStyle: 'short' });
}

export default function SupportTicketDetailPage() {
  const params = useParams();
  const router = useRouter();
  const idParam = params?.id as string | undefined;
  const id = idParam || null;
  const { data, isLoading, error } = useSupportTicketDetail(id);
  const { addComment } = useSupportTicketCommentMutations(id);
  const { assignTicket, overrideSla } = useSupportTicketMutations();
  const { addActivity } = useSupportTicketActivityMutations(id);
  const { addCommunication } = useSupportTicketCommunicationMutations(id);
  const { addDependency } = useSupportTicketDependencyMutations(id);
  const [newComment, setNewComment] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [assignForm, setAssignForm] = useState({ agent_id: '', team_id: '', member_id: '', employee_id: '', assigned_to: '' });
  const [assignError, setAssignError] = useState<string | null>(null);
  const [assigning, setAssigning] = useState(false);
  const [slaForm, setSlaForm] = useState({ response_by: '', resolution_by: '', reason: '' });
  const [slaError, setSlaError] = useState<string | null>(null);
  const [savingSla, setSavingSla] = useState(false);
  const [activityForm, setActivityForm] = useState({ activity_type: 'Status Change', activity: '' });
  const [commForm, setCommForm] = useState({ communication_type: 'Email', communication_medium: 'Email', subject: '', content: '' });
  const [depForm, setDepForm] = useState({ depends_on_ticket_id: '', depends_on_subject: '' });

  if (isLoading) {
    return (
      <div className="bg-slate-card border border-slate-border rounded-xl p-6 space-y-3">
        <div className="h-6 w-32 bg-slate-elevated rounded animate-pulse" />
        <div className="space-y-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-4 bg-slate-elevated rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load ticket</p>
        <button
          onClick={() => router.back()}
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
      </div>
    );
  }

  const ticket = data as any;

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    setAdding(true);
    setAddError(null);
    try {
      await addComment({
        comment: newComment.trim(),
        comment_type: 'Comment',
        is_public: true,
      });
      setNewComment('');
    } catch (err: any) {
      setAddError(err?.message || 'Failed to add comment');
    } finally {
      setAdding(false);
    }
  };

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    if (!assignForm.agent_id && !assignForm.team_id && !assignForm.member_id && !assignForm.employee_id && !assignForm.assigned_to) {
      setAssignError('Provide at least one assignee field');
      return;
    }
    setAssignError(null);
    setAssigning(true);
    try {
      await assignTicket(id, {
        agent_id: assignForm.agent_id ? Number(assignForm.agent_id) : undefined,
        team_id: assignForm.team_id ? Number(assignForm.team_id) : undefined,
        member_id: assignForm.member_id ? Number(assignForm.member_id) : undefined,
        employee_id: assignForm.employee_id ? Number(assignForm.employee_id) : undefined,
        assigned_to: assignForm.assigned_to || undefined,
      });
    } catch (err: any) {
      setAssignError(err?.message || 'Failed to assign ticket');
    } finally {
      setAssigning(false);
    }
  };

  const handleSlaSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setSlaError(null);
    setSavingSla(true);
    try {
      await overrideSla(id, {
        response_by: slaForm.response_by || undefined,
        resolution_by: slaForm.resolution_by || undefined,
        reason: slaForm.reason || undefined,
      });
    } catch (err: any) {
      setSlaError(err?.message || 'Failed to update SLA');
    } finally {
      setSavingSla(false);
    }
  };

  const handleAddActivity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activityForm.activity.trim()) return;
    await addActivity({
      activity_type: activityForm.activity_type || 'Update',
      activity: activityForm.activity.trim(),
    });
    setActivityForm({ activity_type: 'Status Change', activity: '' });
  };

  const handleAddCommunication = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commForm.subject.trim() && !commForm.content.trim()) return;
    await addCommunication({
      communication_type: commForm.communication_type || 'Email',
      communication_medium: commForm.communication_medium || commForm.communication_type || 'Email',
      subject: commForm.subject || undefined,
      content: commForm.content || undefined,
      sent_or_received: 'Received',
    });
    setCommForm({ communication_type: 'Email', communication_medium: 'Email', subject: '', content: '' });
  };

  const handleAddDependency = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!depForm.depends_on_ticket_id && !depForm.depends_on_subject) return;
    await addDependency({
      depends_on_ticket_id: depForm.depends_on_ticket_id ? Number(depForm.depends_on_ticket_id) : undefined,
      depends_on_subject: depForm.depends_on_subject || undefined,
    });
    setDepForm({ depends_on_ticket_id: '', depends_on_subject: '' });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/support/tickets"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to tickets
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Ticket</p>
            <h1 className="text-xl font-semibold text-white">
              {ticket.ticket_number || `Ticket #${ticket.id}`}
            </h1>
            <div className="flex gap-2 mt-1 text-sm">
              <span className="px-2 py-1 rounded-full bg-slate-elevated border border-slate-border text-slate-200">
                Status: {ticket.status || 'Unknown'}
              </span>
              {ticket.priority && (
                <span className="px-2 py-1 rounded-full bg-slate-elevated border border-slate-border text-slate-200">
                  Priority: {ticket.priority}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: 'Subject', value: ticket.subject || '-' },
          { label: 'Owner', value: ticket.owner || ticket.assigned_to || '-' },
          { label: 'Customer', value: ticket.customer_name || ticket.customer || '-' },
          { label: 'Created', value: formatDate(ticket.created_at || ticket.creation) },
          { label: 'Last Updated', value: formatDate(ticket.modified_at || ticket.modified) },
          { label: 'Category', value: ticket.category || '-' },
        ].map((row) => (
          <div key={row.label}>
            <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">{row.label}</p>
            <p className="text-white font-semibold">{row.value}</p>
          </div>
        ))}
      </div>

      <Section
        title="Comments"
        icon={<MessageSquare className="w-4 h-4 text-teal-electric" />}
        emptyText="No comments yet."
        rows={(ticket.comments as any[]) || []}
        renderRow={(c) => (
          <div className="flex flex-col gap-1 border-b border-slate-border/60 pb-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-white font-medium">{c.commented_by_name || c.commented_by || 'Unknown'}</span>
              <span className="text-slate-muted text-xs">{formatDate(c.comment_date || c.created_at)}</span>
            </div>
            <p className="text-slate-200 text-sm whitespace-pre-line">{c.comment}</p>
            <div className="flex gap-2 text-xs text-slate-muted">
              <span>{c.comment_type || 'Comment'}</span>
              <span>&bull;</span>
              <span>{c.is_public ? 'Public' : 'Private'}</span>
            </div>
          </div>
        )}
      />

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Send className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Add comment</h3>
        </div>
        {addError && <p className="text-red-400 text-sm">{addError}</p>}
        <form onSubmit={handleAddComment} className="space-y-3">
          <textarea
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            rows={3}
            className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            placeholder="Write a public comment..."
          />
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={adding}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
            >
              <Send className="w-4 h-4" />
              {adding ? 'Posting...' : 'Post comment'}
            </button>
          </div>
        </form>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Assign ticket</h3>
          </div>
          {assignError && <p className="text-red-400 text-sm">{assignError}</p>}
          <form onSubmit={handleAssign} className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Agent ID</label>
                <input
                  value={assignForm.agent_id}
                  onChange={(e) => setAssignForm((f) => ({ ...f, agent_id: e.target.value }))}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Agent id"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Team ID</label>
                <input
                  value={assignForm.team_id}
                  onChange={(e) => setAssignForm((f) => ({ ...f, team_id: e.target.value }))}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Team id"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Member ID</label>
                <input
                  value={assignForm.member_id}
                  onChange={(e) => setAssignForm((f) => ({ ...f, member_id: e.target.value }))}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Team member id"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Employee ID</label>
                <input
                  value={assignForm.employee_id}
                  onChange={(e) => setAssignForm((f) => ({ ...f, employee_id: e.target.value }))}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Employee id"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Assigned To</label>
                <input
                  value={assignForm.assigned_to}
                  onChange={(e) => setAssignForm((f) => ({ ...f, assigned_to: e.target.value }))}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Display name"
                />
              </div>
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={assigning}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
              >
                {assigning ? 'Saving...' : 'Assign'}
              </button>
            </div>
          </form>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">SLA override</h3>
          </div>
          {slaError && <p className="text-red-400 text-sm">{slaError}</p>}
          <form onSubmit={handleSlaSave} className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Response by</label>
                <input
                  type="datetime-local"
                  value={slaForm.response_by}
                  onChange={(e) => setSlaForm((f) => ({ ...f, response_by: e.target.value }))}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Resolution by</label>
                <input
                  type="datetime-local"
                  value={slaForm.resolution_by}
                  onChange={(e) => setSlaForm((f) => ({ ...f, resolution_by: e.target.value }))}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Reason</label>
              <textarea
                value={slaForm.reason}
                onChange={(e) => setSlaForm((f) => ({ ...f, reason: e.target.value }))}
                rows={3}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="Why the SLA was adjusted"
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={savingSla}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
              >
                {savingSla ? 'Saving...' : 'Save SLA'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Quick add activity */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <ActivitySquare className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Log activity</h3>
        </div>
        <form onSubmit={handleAddActivity} className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <select
            value={activityForm.activity_type}
            onChange={(e) => setActivityForm({ ...activityForm, activity_type: e.target.value })}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="Status Change">Status Change</option>
            <option value="Update">Update</option>
            <option value="Note">Note</option>
          </select>
          <input
            value={activityForm.activity}
            onChange={(e) => setActivityForm({ ...activityForm, activity: e.target.value })}
            placeholder="Activity detail"
            className="md:col-span-2 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <div className="md:col-span-3 flex justify-end">
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90"
            >
              Add activity
            </button>
          </div>
        </form>
      </div>

      {/* Quick add communication */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Mail className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Add communication</h3>
        </div>
        <form onSubmit={handleAddCommunication} className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <input
            value={commForm.subject}
            onChange={(e) => setCommForm({ ...commForm, subject: e.target.value })}
            placeholder="Subject"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <select
            value={commForm.communication_type}
            onChange={(e) => setCommForm({ ...commForm, communication_type: e.target.value })}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="Email">Email</option>
            <option value="Chat">Chat</option>
            <option value="Call">Call</option>
          </select>
          <textarea
            value={commForm.content}
            onChange={(e) => setCommForm({ ...commForm, content: e.target.value })}
            placeholder="Body/content"
            className="md:col-span-2 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50 min-h-[100px]"
          />
          <div className="md:col-span-2 flex justify-end">
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90"
            >
              Add communication
            </button>
          </div>
        </form>
      </div>

      {/* Quick add dependency */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Link2 className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Add dependency</h3>
        </div>
        <form onSubmit={handleAddDependency} className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            value={depForm.depends_on_ticket_id}
            onChange={(e) => setDepForm({ ...depForm, depends_on_ticket_id: e.target.value })}
            placeholder="Depends on ticket ID"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <input
            value={depForm.depends_on_subject}
            onChange={(e) => setDepForm({ ...depForm, depends_on_subject: e.target.value })}
            placeholder="Subject/description"
            className="md:col-span-2 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <div className="md:col-span-3 flex justify-end">
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90"
            >
              Add dependency
            </button>
          </div>
        </form>
      </div>

      <Section
        title="Activities"
        icon={<ActivitySquare className="w-4 h-4 text-teal-electric" />}
        emptyText="No activities yet."
        rows={(ticket.activities as any[]) || []}
        renderRow={(a) => (
          <div className="flex items-start justify-between border-b border-slate-border/60 pb-3">
            <div className="space-y-1">
              <p className="text-white font-semibold">{a.activity_type || 'Activity'}</p>
              <p className="text-slate-200 text-sm whitespace-pre-line">{a.activity}</p>
              {(a.from_status || a.to_status) && (
                <p className="text-xs text-slate-muted">
                  {a.from_status || '-'} → {a.to_status || '-'}
                </p>
              )}
            </div>
            <span className="text-slate-muted text-xs">{formatDate(a.activity_date || a.created_at)}</span>
          </div>
        )}
      />

      <Section
        title="Communications"
        icon={<Mail className="w-4 h-4 text-teal-electric" />}
        emptyText="No communications yet."
        rows={(ticket.communications as any[]) || []}
        renderRow={(c) => (
          <div className="flex flex-col gap-1 border-b border-slate-border/60 pb-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-white font-semibold">{c.subject || c.communication_type || 'Communication'}</span>
              <span className="text-slate-muted text-xs">{formatDate(c.communication_date)}</span>
            </div>
            <p className="text-slate-muted text-xs">
              {c.communication_type || c.communication_medium || '-'} &bull; {c.sent_or_received || '-'}
            </p>
            <p className="text-slate-200 text-sm whitespace-pre-line line-clamp-3">{c.content || '-'}</p>
            <p className="text-xs text-slate-muted">
              From {c.sender_full_name || c.sender || '-'} → {c.recipients || '-'}
            </p>
          </div>
        )}
      />

      <Section
        title="Dependencies"
        icon={<Link2 className="w-4 h-4 text-teal-electric" />}
        emptyText="No linked tickets."
        rows={(ticket.depends_on as any[]) || []}
        renderRow={(d) => (
          <div className="flex items-center justify-between border-b border-slate-border/60 pb-3">
            <div className="space-y-1">
              <p className="text-white font-semibold">{d.depends_on_subject || d.depends_on_ticket_id || 'Linked ticket'}</p>
              <p className="text-xs text-slate-muted">Status: {d.depends_on_status || '-'}</p>
            </div>
            <span className="text-slate-muted text-xs">{d.depends_on_erpnext_id || d.depends_on_ticket_id || ''}</span>
          </div>
        )}
      />

      <Section
        title="Expenses"
        icon={<Receipt className="w-4 h-4 text-teal-electric" />}
        emptyText="No expenses attached."
        rows={(ticket.expenses as any[]) || []}
        renderRow={(e) => (
          <div className="flex items-start justify-between border-b border-slate-border/60 pb-3">
            <div className="space-y-1">
              <p className="text-white font-semibold">{e.expense_type || 'Expense'}</p>
              <p className="text-slate-200 text-sm">{e.description || '-'}</p>
              <p className="text-xs text-slate-muted">
                Claimed: {e.total_claimed_amount ?? 0} &bull; Sanctioned: {e.total_sanctioned_amount ?? 0}
              </p>
              <p className="text-xs text-slate-muted">Status: {e.status || '-'}</p>
            </div>
            <span className="text-slate-muted text-xs">{formatDate(e.expense_date)}</span>
          </div>
        )}
      />
    </div>
  );
}

function Section({
  title,
  icon,
  rows,
  renderRow,
  emptyText,
}: {
  title: string;
  icon: React.ReactNode;
  rows: any[];
  renderRow: (row: any) => React.ReactNode;
  emptyText: string;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        {icon}
        <h3 className="text-white font-semibold">{title}</h3>
      </div>
      {rows.length === 0 ? (
        <p className="text-slate-muted text-sm">{emptyText}</p>
      ) : (
        <div className="space-y-3">{rows.map((row, idx) => <div key={idx}>{renderRow(row)}</div>)}</div>
      )}
    </div>
  );
}
