'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, LifeBuoy, User, Users, Tag, Clock } from 'lucide-react';
import { useSupportTicketMutations, useSupportAgents, useSupportTeams } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { useRequireScope } from '@/lib/auth-context';
import { useFormErrors } from '@/hooks';
import { AccessDenied } from '@/components/AccessDenied';
import { Button } from '@/components/ui';

export default function SupportTicketCreatePage() {
  const router = useRouter();
  const { createTicket } = useSupportTicketMutations();
  const { hasAccess: canWrite, isLoading: authLoading } = useRequireScope('support:write');
  const canFetch = canWrite && !authLoading;
  const { data: agentsData } = useSupportAgents(undefined, undefined, { isPaused: () => !canFetch });
  const { data: teamsData } = useSupportTeams({ isPaused: () => !canFetch });
  const { errors: fieldErrors, setErrors } = useFormErrors();

  const agents = agentsData?.agents?.filter((a: any) => a.is_active) || [];
  const teams = teamsData?.teams || [];

  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState('open');
  const [priority, setPriority] = useState('medium');
  const [ticketType, setTicketType] = useState('');
  const [issueType, setIssueType] = useState('');
  const [agentId, setAgentId] = useState('');
  const [teamId, setTeamId] = useState('');
  const [resolutionBy, setResolutionBy] = useState('');
  const [responseBy, setResponseBy] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [region, setRegion] = useState('');
  const [baseStation, setBaseStation] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-electric" />
      </div>
    );
  }

  if (!canWrite) {
    return (
      <div className="min-h-screen bg-slate-deep p-8">
        <AccessDenied />
      </div>
    );
  }

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!subject.trim()) errs.subject = 'Subject is required';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!validate()) return;
    setSubmitting(true);
    try {
      // Get assigned_to name from selected agent
      const selectedAgent = agents.find((a: any) => a.id === Number(agentId));
      const selectedTeam = teams.find((t: any) => t.id === Number(teamId));

      const payload = {
        subject: subject.trim(),
        description: description || undefined,
        status: status as any,
        priority: priority as any,
        ticket_type: ticketType || undefined,
        issue_type: issueType || undefined,
        assigned_to: selectedAgent?.display_name || selectedAgent?.email || undefined,
        assigned_employee_id: selectedAgent?.employee_id || undefined,
        resolution_team: selectedTeam?.team_name || undefined,
        resolution_by: resolutionBy || undefined,
        response_by: responseBy || undefined,
        customer_email: customerEmail || undefined,
        customer_phone: customerPhone || undefined,
        customer_name: customerName || undefined,
        region: region || undefined,
        base_station: baseStation || undefined,
      };
      const res = await createTicket(payload);
      router.push(`/support/tickets/${res.id}`);
    } catch (err: any) {
      setError(err?.message || 'Failed to create ticket');
    } finally {
      setSubmitting(false);
    }
  };

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
              <h1 className="text-2xl font-bold text-foreground">New Ticket</h1>
              <p className="text-slate-muted text-sm">Ticket number auto-generates on create</p>
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left Column - Basic Info */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-border">
            <Tag className="w-4 h-4 text-teal-electric" />
            <h2 className="text-foreground font-semibold">Ticket Details</h2>
          </div>

          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Subject *</label>
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className={cn(
                'w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50',
                fieldErrors.subject && 'border-red-500/60'
              )}
              placeholder="Brief description of the issue"
            />
            {fieldErrors.subject && <p className="text-xs text-red-400">{fieldErrors.subject}</p>}
          </div>

          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              placeholder="Steps to reproduce, impact, etc."
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="open">Open</option>
                <option value="replied">Replied</option>
                <option value="resolved">Resolved</option>
                <option value="closed">Closed</option>
                <option value="on_hold">On Hold</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Ticket Type</label>
              <input
                value={ticketType}
                onChange={(e) => setTicketType(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="Support / Incident / etc."
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Issue Type</label>
              <input
                value={issueType}
                onChange={(e) => setIssueType(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="Outage / Billing / etc."
              />
            </div>
          </div>
        </div>

        {/* Right Column - Assignment & Customer */}
        <div className="space-y-4">
          {/* Assignment */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-border">
              <Users className="w-4 h-4 text-teal-electric" />
              <h2 className="text-foreground font-semibold">Assignment</h2>
            </div>

            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Assign to Agent</label>
              <select
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                <option value="">-- Select an agent --</option>
                {agents.map((agent: any) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.display_name || agent.email} {agent.capacity ? `(${agent.capacity} capacity)` : ''}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Resolution Team</label>
              <select
                value={teamId}
                onChange={(e) => setTeamId(e.target.value)}
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

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Response By</label>
                <input
                  type="datetime-local"
                  value={responseBy}
                  onChange={(e) => setResponseBy(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Resolution By</label>
                <input
                  type="datetime-local"
                  value={resolutionBy}
                  onChange={(e) => setResolutionBy(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                />
              </div>
            </div>
          </div>

          {/* Customer */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-border">
              <User className="w-4 h-4 text-teal-electric" />
              <h2 className="text-foreground font-semibold">Customer Information</h2>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Customer Name</label>
                <input
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Full name"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Customer Email</label>
                <input
                  type="email"
                  value={customerEmail}
                  onChange={(e) => setCustomerEmail(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="customer@email.com"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Customer Phone</label>
                <input
                  value={customerPhone}
                  onChange={(e) => setCustomerPhone(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="+234..."
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Region</label>
                <input
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="Lagos, Abuja, etc."
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Base Station</label>
              <input
                value={baseStation}
                onChange={(e) => setBaseStation(e.target.value)}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="Station identifier"
              />
            </div>
          </div>
        </div>

        {/* Form Actions */}
        <div className="lg:col-span-2 flex justify-end gap-3">
          <Button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={submitting}
            className="px-6 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
          >
            {submitting ? 'Creating...' : 'Create Ticket'}
          </Button>
        </div>
      </form>
    </div>
  );
}
