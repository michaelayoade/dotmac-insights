'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Plus,
  Search,
  Filter,
  MoreHorizontal,
  Target,
  DollarSign,
  Calendar,
  User,
  Building2,
  TrendingUp,
  TrendingDown,
  Clock,
} from 'lucide-react';
import { useOpportunities, usePipelineSummary, usePipelineStages } from '@/hooks/useApi';
import { formatDate, formatDistanceToNow } from '@/lib/date';
import type { PipelineStage, Opportunity } from '@/lib/api';

const statusColors: Record<string, string> = {
  open: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  won: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  lost: 'bg-red-500/20 text-red-400 border-red-500/30',
};

export default function OpportunitiesPage() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');
  const [stageId, setStageId] = useState<string>('');
  const [page, setPage] = useState(1);

  const { data: opportunities, isLoading } = useOpportunities({
    search: search || undefined,
    status: status || undefined,
    stage_id: stageId ? parseInt(stageId) : undefined,
    page,
    page_size: 20,
  });

  const { data: summary } = usePipelineSummary();
  const { data: stages } = usePipelineStages();

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency: 'NGN',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Opportunities</h1>
          <p className="text-sm text-slate-400 mt-1">
            Track deals through your sales pipeline
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/sales/pipeline"
            className="flex items-center gap-2 px-4 py-2 bg-slate-700/50 hover:bg-slate-700 text-white rounded-lg transition-colors"
          >
            <Target className="w-4 h-4" />
            Pipeline View
          </Link>
          <Link
            href="/sales/opportunities/new"
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Opportunity
          </Link>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
            <div className="text-sm text-slate-400">Open Deals</div>
            <div className="text-2xl font-semibold text-white mt-1">{summary.open_count || 0}</div>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
            <div className="text-sm text-slate-400">Pipeline Value</div>
            <div className="text-2xl font-semibold text-emerald-400 mt-1">
              {formatCurrency(summary.total_value || 0)}
            </div>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
            <div className="text-sm text-slate-400">Weighted Value</div>
            <div className="text-2xl font-semibold text-cyan-400 mt-1">
              {formatCurrency(summary.weighted_value || 0)}
            </div>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
            <div className="text-sm text-slate-400">Win Rate</div>
            <div className="text-2xl font-semibold text-amber-400 mt-1">
              {summary.win_rate?.toFixed(1) || 0}%
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search opportunities..."
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
          <option value="open">Open</option>
          <option value="won">Won</option>
          <option value="lost">Lost</option>
        </select>
        <select
          value={stageId}
          onChange={(e) => setStageId(e.target.value)}
          className="px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
        >
          <option value="">All Stages</option>
          {stages?.map((stage: PipelineStage) => (
            <option key={stage.id} value={stage.id}>{stage.name}</option>
          ))}
        </select>
      </div>

      {/* Opportunities Table */}
      <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-400" />
          </div>
        ) : opportunities?.items?.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-400">
            <Target className="w-12 h-12 mb-4 opacity-50" />
            <p>No opportunities found</p>
            <Link
              href="/sales/opportunities/new"
              className="mt-4 text-emerald-400 hover:text-emerald-300"
            >
              Create your first opportunity
            </Link>
          </div>
        ) : (
          <>
            {/* Table Header */}
            <div className="grid grid-cols-12 gap-4 px-4 py-3 bg-slate-800/50 text-xs font-medium text-slate-400 uppercase tracking-wider">
              <div className="col-span-4">Opportunity</div>
              <div className="col-span-2">Stage</div>
              <div className="col-span-2 text-right">Value</div>
              <div className="col-span-1 text-center">Prob.</div>
              <div className="col-span-2">Expected Close</div>
              <div className="col-span-1"></div>
            </div>

            {/* Table Body */}
            <div className="divide-y divide-slate-700/50">
              {opportunities?.items?.map((opp: Opportunity) => (
                <Link
                  key={opp.id}
                  href={`/sales/opportunities/${opp.id}`}
                  className="grid grid-cols-12 gap-4 px-4 py-4 hover:bg-slate-700/30 transition-colors items-center"
                >
                  {/* Opportunity Name & Customer */}
                  <div className="col-span-4">
                    <div className="font-medium text-white">{opp.name}</div>
                    <div className="text-sm text-slate-400 flex items-center gap-1 mt-0.5">
                      {opp.customer_name ? (
                        <>
                          <Building2 className="w-3 h-3" />
                          {opp.customer_name}
                        </>
                      ) : opp.lead_name ? (
                        <>
                          <User className="w-3 h-3" />
                          {opp.lead_name}
                        </>
                      ) : null}
                    </div>
                  </div>

                  {/* Stage */}
                  <div className="col-span-2">
                    {opp.stage_name ? (
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${statusColors[opp.status] || statusColors.open}`}>
                        {opp.stage_name}
                      </span>
                    ) : (
                      <span className="text-slate-500 text-sm">No stage</span>
                    )}
                  </div>

                  {/* Value */}
                  <div className="col-span-2 text-right">
                    <div className="font-medium text-white">
                      {formatCurrency(opp.deal_value || 0)}
                    </div>
                    <div className="text-xs text-slate-500">
                      Wtd: {formatCurrency(opp.weighted_value || 0)}
                    </div>
                  </div>

                  {/* Probability */}
                  <div className="col-span-1 text-center">
                    <div className={`inline-flex items-center justify-center w-10 h-10 rounded-full text-sm font-medium ${
                      opp.probability >= 70 ? 'bg-emerald-500/20 text-emerald-400' :
                      opp.probability >= 40 ? 'bg-amber-500/20 text-amber-400' :
                      'bg-slate-500/20 text-slate-400'
                    }`}>
                      {opp.probability}%
                    </div>
                  </div>

                  {/* Expected Close */}
                  <div className="col-span-2">
                    {opp.expected_close_date ? (
                      <div className="flex items-center gap-1.5 text-sm">
                        <Calendar className="w-3 h-3 text-slate-400" />
                        <span className="text-white">
                          {formatDate(new Date(opp.expected_close_date), 'MMM d, yyyy')}
                        </span>
                      </div>
                    ) : (
                      <span className="text-slate-500 text-sm">Not set</span>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="col-span-1 flex justify-end">
                    <button
                      onClick={(e) => e.preventDefault()}
                      className="p-1.5 text-slate-400 hover:bg-slate-700/50 rounded-lg transition-colors"
                    >
                      <MoreHorizontal className="w-4 h-4" />
                    </button>
                  </div>
                </Link>
              ))}
            </div>
          </>
        )}

        {/* Pagination */}
        {opportunities && opportunities.total > 20 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700/50">
            <div className="text-sm text-slate-400">
              Showing {((page - 1) * 20) + 1} to {Math.min(page * 20, opportunities.total)} of {opportunities.total}
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
                disabled={page * 20 >= opportunities.total}
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
