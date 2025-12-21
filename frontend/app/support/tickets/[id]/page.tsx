'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  Clock,
  LifeBuoy,
  MessageSquare,
  ActivitySquare,
  Mail,
  Link2,
  Receipt,
  Send,
  Users,
  ShieldCheck,
  User,
  Tag,
  Eye,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import {
  useSupportTicketDetail,
  useSupportTicketCommentMutations,
  useSupportTicketMutations,
  useSupportTicketActivityMutations,
  useSupportTicketCommunicationMutations,
  useSupportTicketDependencyMutations,
  useSupportAgents,
  useSupportTeams,
} from '@/hooks/useApi';
import { cn } from '@/lib/utils';

function formatDate(value?: string | null) {
  if (!value) return '-';
  const dt = new Date(value);
  return dt.toLocaleString('en-NG', { dateStyle: 'medium', timeStyle: 'short' });
}

function formatTimeAgo(dateStr: string | null | undefined) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHours > 0) return `${diffHours}h ago`;
  return 'Just now';
}

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    urgent: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    high: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
    medium: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    low: 'bg-slate-500/10 text-foreground-secondary border-slate-500/30',
  };
  const color = colors[priority] || colors.medium;

  return (
    <span className={cn('px-2 py-1 rounded-full text-xs font-medium border inline-flex items-center gap-1', color)}>
      <Tag className="w-3 h-3" />
      {priority}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    open: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    in_progress: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    pending: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    resolved: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    closed: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
    replied: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
    on_hold: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
  };
  const color = colors[status] || colors.open;

  return (
    <span className={cn('px-2 py-1 rounded-full text-xs font-medium border capitalize', color)}>
      {status?.replace(/_/g, ' ')}
    </span>
  );
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

  // Fetch agents and teams for dropdowns
  const { data: agentsData } = useSupportAgents();
  const { data: teamsData } = useSupportTeams();
  const agents = agentsData?.agents || [];
  const teams = teamsData?.teams || [];

  const [newComment, setNewComment] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [assignForm, setAssignForm] = useState({ agent_id: '', team_id: '', assigned_to: '' });
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
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
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
    if (!assignForm.agent_id && !assignForm.team_id && !assignForm.assigned_to) {
      setAssignError('Select an agent, team, or enter an assignee name');
      return;
    }
    setAssignError(null);
    setAssigning(true);
    try {
      const selectedAgent = agents.find((a: any) => a.id === Number(assignForm.agent_id));
      await assignTicket(id, {
        agent_id: assignForm.agent_id ? Number(assignForm.agent_id) : undefined,
        team_id: assignForm.team_id ? Number(assignForm.team_id) : undefined,
        assigned_to: assignForm.assigned_to || selectedAgent?.display_name || selectedAgent?.email || undefined,
      });
      setAssignForm({ agent_id: '', team_id: '', assigned_to: '' });
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

  const isOverdue = ticket.resolution_by && new Date(ticket.resolution_by) < new Date() && !['resolved', 'closed'].includes(ticket.status);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/support/tickets"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-teal-electric/10 border border-teal-electric/30 flex items-center justify-center">
              <LifeBuoy className="w-5 h-5 text-teal-electric" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-semibold text-foreground">
                  {ticket.ticket_number || `#${ticket.id}`}
                </h1>
                {isOverdue && (
                  <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 text-xs font-medium">
                    OVERDUE
                  </span>
                )}
              </div>
              <p className="text-slate-muted text-sm">{ticket.subject || 'No subject'}</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={ticket.status || 'open'} />
          <PriorityBadge priority={ticket.priority || 'medium'} />
        </div>
      </div>

      {/* Ticket Info Card */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="space-y-3">
            <h3 className="text-foreground font-semibold flex items-center gap-2">
              <User className="w-4 h-4 text-teal-electric" />
              Customer
            </h3>
            <div className="space-y-1">
              <p className="text-foreground font-medium">{ticket.customer_name || 'Unknown'}</p>
              {ticket.customer_email && (
                <p className="text-slate-muted text-sm">{ticket.customer_email}</p>
              )}
              {ticket.customer_phone && (
                <p className="text-slate-muted text-sm">{ticket.customer_phone}</p>
              )}
              {ticket.region && (
                <p className="text-slate-muted text-xs">Region: {ticket.region}</p>
              )}
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-foreground font-semibold flex items-center gap-2">
              <Users className="w-4 h-4 text-teal-electric" />
              Assignment
            </h3>
            <div className="space-y-1">
              <p className={cn('text-sm', ticket.assigned_to ? 'text-foreground' : 'text-amber-400')}>
                {ticket.assigned_to || 'Unassigned'}
              </p>
              {ticket.resolution_team && (
                <p className="text-slate-muted text-sm">Team: {ticket.resolution_team}</p>
              )}
              {ticket.owner && (
                <p className="text-slate-muted text-xs">Owner: {ticket.owner}</p>
              )}
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-foreground font-semibold flex items-center gap-2">
              <Tag className="w-4 h-4 text-teal-electric" />
              Details
            </h3>
            <div className="space-y-1">
              {ticket.ticket_type && (
                <p className="text-slate-200 text-sm">Type: {ticket.ticket_type}</p>
              )}
              {ticket.issue_type && (
                <p className="text-slate-200 text-sm">Issue: {ticket.issue_type}</p>
              )}
              {ticket.category && (
                <p className="text-slate-200 text-sm">Category: {ticket.category}</p>
              )}
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-foreground font-semibold flex items-center gap-2">
              <Clock className="w-4 h-4 text-teal-electric" />
              SLA & Dates
            </h3>
            <div className="space-y-1">
              <p className="text-slate-muted text-sm">
                Created: {formatDate(ticket.created_at || ticket.creation)}
              </p>
              {ticket.response_by && (
                <p className="text-slate-muted text-sm">
                  Response by: {formatDate(ticket.response_by)}
                </p>
              )}
              {ticket.resolution_by && (
                <p className={cn('text-sm', isOverdue ? 'text-rose-400' : 'text-slate-muted')}>
                  Resolution by: {formatDate(ticket.resolution_by)}
                </p>
              )}
            </div>
          </div>
        </div>

        {ticket.description && (
          <div className="mt-4 pt-4 border-t border-slate-border">
            <h3 className="text-foreground font-semibold mb-2">Description</h3>
            <p className="text-slate-200 text-sm whitespace-pre-line">{ticket.description}</p>
          </div>
        )}

        {/* Tags */}
        {ticket.tags?.length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-border">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-slate-muted text-sm">Tags:</span>
              {ticket.tags.map((tag: any, idx: number) => (
                <span key={idx} className="px-2 py-1 rounded bg-slate-elevated text-slate-200 text-xs">
                  {tag.tag_name || tag.name || tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Watchers */}
        {ticket.watchers?.length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-border">
            <div className="flex items-center gap-2 flex-wrap">
              <Eye className="w-4 h-4 text-slate-muted" />
              <span className="text-slate-muted text-sm">Watchers:</span>
              {ticket.watchers.map((w: any, idx: number) => (
                <span key={idx} className="text-slate-200 text-sm">
                  {w.watcher_name || w.watcher || w}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Comments Section */}
      <Section
        title="Comments"
        icon={<MessageSquare className="w-4 h-4 text-teal-electric" />}
        emptyText="No comments yet."
        rows={(ticket.comments as any[]) || []}
        renderRow={(c) => (
          <div className="flex flex-col gap-1 border-b border-slate-border/60 pb-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-foreground font-medium">{c.commented_by_name || c.commented_by || 'Unknown'}</span>
              <div className="flex items-center gap-2">
                <span className="text-slate-muted text-xs">{formatTimeAgo(c.comment_date || c.created_at)}</span>
                <span className="text-slate-muted text-xs">{formatDate(c.comment_date || c.created_at)}</span>
              </div>
            </div>
            <p className="text-slate-200 text-sm whitespace-pre-line">{c.comment}</p>
            <div className="flex gap-2 text-xs text-slate-muted">
              <span className="px-2 py-0.5 rounded bg-slate-elevated">{c.comment_type || 'Comment'}</span>
              <span className={cn(
                'px-2 py-0.5 rounded',
                c.is_public ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'
              )}>
                {c.is_public ? 'Public' : 'Private'}
              </span>
            </div>
          </div>
        )}
      />

      {/* Add Comment Form */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Send className="w-4 h-4 text-teal-electric" />
          <h3 className="text-foreground font-semibold">Add comment</h3>
        </div>
        {addError && <p className="text-red-400 text-sm">{addError}</p>}
        <form onSubmit={handleAddComment} className="space-y-3">
          <textarea
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            rows={3}
            className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
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

      {/* Assignment & SLA Override */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Assignment Form */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">Assign ticket</h3>
          </div>
          {assignError && <p className="text-red-400 text-sm">{assignError}</p>}
          <form onSubmit={handleAssign} className="space-y-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Select Agent</label>
              <select
                value={assignForm.agent_id}
                onChange={(e) => setAssignForm((f) => ({ ...f, agent_id: e.target.value }))}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="">-- Select an agent --</option>
                {agents.filter((a: any) => a.is_active).map((agent: any) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.display_name || agent.email} {agent.capacity ? `(${agent.capacity} capacity)` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Select Team</label>
              <select
                value={assignForm.team_id}
                onChange={(e) => setAssignForm((f) => ({ ...f, team_id: e.target.value }))}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="">-- Select a team --</option>
                {teams.map((team: any) => (
                  <option key={team.id} value={team.id}>
                    {team.team_name} {team.description ? `(${team.description})` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Or enter assignee name</label>
              <input
                value={assignForm.assigned_to}
                onChange={(e) => setAssignForm((f) => ({ ...f, assigned_to: e.target.value }))}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="Display name or email"
              />
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

        {/* SLA Override Form */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-teal-electric" />
            <h3 className="text-foreground font-semibold">SLA override</h3>
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
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Resolution by</label>
                <input
                  type="datetime-local"
                  value={slaForm.resolution_by}
                  onChange={(e) => setSlaForm((f) => ({ ...f, resolution_by: e.target.value }))}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Reason</label>
              <textarea
                value={slaForm.reason}
                onChange={(e) => setSlaForm((f) => ({ ...f, reason: e.target.value }))}
                rows={2}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
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
          <h3 className="text-foreground font-semibold">Log activity</h3>
        </div>
        <form onSubmit={handleAddActivity} className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <select
            value={activityForm.activity_type}
            onChange={(e) => setActivityForm({ ...activityForm, activity_type: e.target.value })}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="Status Change">Status Change</option>
            <option value="Update">Update</option>
            <option value="Note">Note</option>
          </select>
          <input
            value={activityForm.activity}
            onChange={(e) => setActivityForm({ ...activityForm, activity: e.target.value })}
            placeholder="Activity detail"
            className="md:col-span-2 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
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
          <h3 className="text-foreground font-semibold">Add communication</h3>
        </div>
        <form onSubmit={handleAddCommunication} className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <input
            value={commForm.subject}
            onChange={(e) => setCommForm({ ...commForm, subject: e.target.value })}
            placeholder="Subject"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <select
            value={commForm.communication_type}
            onChange={(e) => setCommForm({ ...commForm, communication_type: e.target.value })}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="Email">Email</option>
            <option value="Chat">Chat</option>
            <option value="Call">Call</option>
          </select>
          <textarea
            value={commForm.content}
            onChange={(e) => setCommForm({ ...commForm, content: e.target.value })}
            placeholder="Body/content"
            className="md:col-span-2 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50 min-h-[100px]"
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
          <h3 className="text-foreground font-semibold">Add dependency</h3>
        </div>
        <form onSubmit={handleAddDependency} className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            value={depForm.depends_on_ticket_id}
            onChange={(e) => setDepForm({ ...depForm, depends_on_ticket_id: e.target.value })}
            placeholder="Depends on ticket ID"
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <input
            value={depForm.depends_on_subject}
            onChange={(e) => setDepForm({ ...depForm, depends_on_subject: e.target.value })}
            placeholder="Subject/description"
            className="md:col-span-2 bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
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
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-slate-elevated text-slate-200 text-xs">{a.activity_type || 'Activity'}</span>
                {(a.from_status || a.to_status) && (
                  <span className="text-xs text-slate-muted">
                    {a.from_status || '-'} → {a.to_status || '-'}
                  </span>
                )}
              </div>
              <p className="text-slate-200 text-sm whitespace-pre-line">{a.activity}</p>
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
              <span className="text-foreground font-semibold">{c.subject || c.communication_type || 'Communication'}</span>
              <span className="text-slate-muted text-xs">{formatDate(c.communication_date)}</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="px-2 py-0.5 rounded bg-slate-elevated text-slate-muted">
                {c.communication_type || c.communication_medium || '-'}
              </span>
              <span className={cn(
                'px-2 py-0.5 rounded',
                c.sent_or_received === 'Sent' ? 'bg-blue-500/10 text-blue-400' : 'bg-emerald-500/10 text-emerald-400'
              )}>
                {c.sent_or_received || '-'}
              </span>
            </div>
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
              <p className="text-foreground font-semibold">{d.depends_on_subject || `Ticket #${d.depends_on_ticket_id}`}</p>
              <p className="text-xs text-slate-muted">Status: {d.depends_on_status || '-'}</p>
            </div>
            <span className="text-slate-muted text-xs font-mono">{d.depends_on_erpnext_id || d.depends_on_ticket_id || ''}</span>
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
              <p className="text-foreground font-semibold">{e.expense_type || 'Expense'}</p>
              <p className="text-slate-200 text-sm">{e.description || '-'}</p>
              <div className="flex gap-3 text-xs text-slate-muted">
                <span>Claimed: {e.total_claimed_amount ?? 0}</span>
                <span>Sanctioned: {e.total_sanctioned_amount ?? 0}</span>
                <span className="px-2 py-0.5 rounded bg-slate-elevated">{e.status || '-'}</span>
              </div>
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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <h3 className="text-foreground font-semibold">{title}</h3>
        </div>
        <span className="text-xs text-slate-muted">{rows.length} items</span>
      </div>
      {rows.length === 0 ? (
        <p className="text-slate-muted text-sm">{emptyText}</p>
      ) : (
        <div className="space-y-3">{rows.map((row, idx) => <div key={idx}>{renderRow(row)}</div>)}</div>
      )}
    </div>
  );
}
