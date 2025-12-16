'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Plus,
  Search,
  Filter,
  MoreHorizontal,
  UserPlus,
  Phone,
  Mail,
  Building2,
  ArrowRight,
  CheckCircle,
  XCircle,
  Clock,
} from 'lucide-react';
import { useLeads, useLeadsSummary, useLeadMutations, useLeadSources } from '@/hooks/useApi';
import { formatDistanceToNow } from '@/lib/date';
import type { Lead } from '@/lib/api';

const statusColors: Record<string, string> = {
  new: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  contacted: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  qualified: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  unqualified: 'bg-red-500/20 text-red-400 border-red-500/30',
  converted: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
};

const statusIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  new: Clock,
  contacted: Phone,
  qualified: CheckCircle,
  unqualified: XCircle,
  converted: ArrowRight,
};

export default function LeadsPage() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');
  const [page, setPage] = useState(1);

  const { data: leads, isLoading } = useLeads({
    search: search || undefined,
    status: status || undefined,
    page,
    page_size: 20,
  });

  const { data: summary } = useLeadsSummary();
  const { data: sources } = useLeadSources();
  const { qualifyLead, disqualifyLead } = useLeadMutations();

  const handleQualify = async (id: number) => {
    try {
      await qualifyLead(id);
    } catch (error) {
      console.error('Failed to qualify lead:', error);
    }
  };

  const handleDisqualify = async (id: number, reason?: string) => {
    try {
      await disqualifyLead(id, reason);
    } catch (error) {
      console.error('Failed to disqualify lead:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Leads</h1>
          <p className="text-sm text-slate-400 mt-1">
            Capture and qualify potential customers
          </p>
        </div>
        <Link
          href="/sales/leads/new"
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Lead
        </Link>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
            <div className="text-sm text-slate-400">Total Leads</div>
            <div className="text-2xl font-semibold text-white mt-1">{summary.total || 0}</div>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
            <div className="text-sm text-blue-400">New</div>
            <div className="text-2xl font-semibold text-white mt-1">{summary.new || 0}</div>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
            <div className="text-sm text-amber-400">Contacted</div>
            <div className="text-2xl font-semibold text-white mt-1">{summary.contacted || 0}</div>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
            <div className="text-sm text-emerald-400">Qualified</div>
            <div className="text-2xl font-semibold text-white mt-1">{summary.qualified || 0}</div>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
            <div className="text-sm text-violet-400">Converted</div>
            <div className="text-2xl font-semibold text-white mt-1">{summary.converted || 0}</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search leads..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          />
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
        >
          <option value="">All Status</option>
          <option value="new">New</option>
          <option value="contacted">Contacted</option>
          <option value="qualified">Qualified</option>
          <option value="unqualified">Unqualified</option>
          <option value="converted">Converted</option>
        </select>
      </div>

      {/* Leads List */}
      <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-400" />
          </div>
        ) : leads?.items?.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-400">
            <UserPlus className="w-12 h-12 mb-4 opacity-50" />
            <p>No leads found</p>
            <Link
              href="/sales/leads/new"
              className="mt-4 text-emerald-400 hover:text-emerald-300"
            >
              Create your first lead
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-slate-700/50">
            {leads?.items?.map((lead: Lead) => {
              const StatusIcon = statusIcons[lead.status] || Clock;
              return (
                <Link
                  key={lead.id}
                  href={`/sales/leads/${lead.id}`}
                  className="flex items-center gap-4 p-4 hover:bg-slate-700/30 transition-colors"
                >
                  {/* Avatar */}
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white font-medium">
                    {lead.lead_name?.charAt(0) || lead.company_name?.charAt(0) || '?'}
                  </div>

                  {/* Main Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-white truncate">
                        {lead.lead_name || 'No Name'}
                      </span>
                      {lead.company_name && (
                        <>
                          <span className="text-slate-500">@</span>
                          <span className="text-slate-400 truncate flex items-center gap-1">
                            <Building2 className="w-3 h-3" />
                            {lead.company_name}
                          </span>
                        </>
                      )}
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-sm text-slate-400">
                      {lead.email_id && (
                        <span className="flex items-center gap-1">
                          <Mail className="w-3 h-3" />
                          {lead.email_id}
                        </span>
                      )}
                      {lead.phone && (
                        <span className="flex items-center gap-1">
                          <Phone className="w-3 h-3" />
                          {lead.phone}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Source */}
                  {lead.source && (
                    <div className="text-sm text-slate-500">
                      {lead.source}
                    </div>
                  )}

                  {/* Status Badge */}
                  <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${statusColors[lead.status] || statusColors.new}`}>
                    <StatusIcon className="w-3 h-3" />
                    {lead.status}
                  </div>

                  {/* Time */}
                  <div className="text-xs text-slate-500 w-24 text-right">
                    {lead.created_at && formatDistanceToNow(lead.created_at)}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    {lead.status === 'new' || lead.status === 'contacted' ? (
                      <>
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            handleQualify(lead.id);
                          }}
                          className="p-1.5 text-emerald-400 hover:bg-emerald-500/20 rounded-lg transition-colors"
                          title="Qualify Lead"
                        >
                          <CheckCircle className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            handleDisqualify(lead.id, 'Not a fit');
                          }}
                          className="p-1.5 text-red-400 hover:bg-red-500/20 rounded-lg transition-colors"
                          title="Disqualify Lead"
                        >
                          <XCircle className="w-4 h-4" />
                        </button>
                      </>
                    ) : null}
                    <button
                      onClick={(e) => e.preventDefault()}
                      className="p-1.5 text-slate-400 hover:bg-slate-700/50 rounded-lg transition-colors"
                    >
                      <MoreHorizontal className="w-4 h-4" />
                    </button>
                  </div>
                </Link>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {leads && leads.total > 20 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700/50">
            <div className="text-sm text-slate-400">
              Showing {((page - 1) * 20) + 1} to {Math.min(page * 20, leads.total)} of {leads.total}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-sm bg-slate-700/50 hover:bg-slate-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={page * 20 >= leads.total}
                className="px-3 py-1.5 text-sm bg-slate-700/50 hover:bg-slate-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
