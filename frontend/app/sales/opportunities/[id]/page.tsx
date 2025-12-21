'use client';

import { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  DollarSign,
  Calendar,
  Building2,
  User,
  CheckCircle,
  XCircle,
  Edit,
  Phone,
  Mail,
  MessageSquare,
  FileText,
  ShoppingCart,
  ChevronRight,
  Target,
  Clock,
} from 'lucide-react';
import { useOpportunity, useOpportunityMutations, usePipelineStages, useActivityTimeline, useCustomerContacts } from '@/hooks/useApi';
import { formatDate, formatDistanceToNow } from '@/lib/date';
import type { PipelineStage, Activity, Contact } from '@/lib/api';

const statusColors: Record<string, string> = {
  open: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  won: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  lost: 'bg-red-500/20 text-red-400 border-red-500/30',
};

export default function OpportunityDetailPage() {
  const router = useRouter();
  const params = useParams();
  const oppId = params.id as string;

  const { data: opportunity, isLoading, error } = useOpportunity(oppId);
  const { data: stages } = usePipelineStages();
  const { data: activities } = useActivityTimeline({ opportunity_id: parseInt(oppId), limit: 10 });
  const { data: contacts } = useCustomerContacts(opportunity?.customer_id || undefined);
  const { moveStage, markWon, markLost } = useOpportunityMutations();

  const [showWonModal, setShowWonModal] = useState(false);
  const [showLostModal, setShowLostModal] = useState(false);
  const [lostReason, setLostReason] = useState('');
  const [competitor, setCompetitor] = useState('');
  const [actualCloseDate, setActualCloseDate] = useState(formatDate(new Date(), 'yyyy-MM-dd'));

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency: 'NGN',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const handleMoveStage = async (stageId: number) => {
    try {
      await moveStage(oppId, stageId);
    } catch (error) {
      console.error('Failed to move stage:', error);
    }
  };

  const handleMarkWon = async () => {
    try {
      await markWon(oppId, actualCloseDate);
      setShowWonModal(false);
    } catch (error) {
      console.error('Failed to mark as won:', error);
    }
  };

  const handleMarkLost = async () => {
    try {
      await markLost(oppId, lostReason, competitor);
      setShowLostModal(false);
    } catch (error) {
      console.error('Failed to mark as lost:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-400" />
      </div>
    );
  }

  if (error || !opportunity) {
    return (
      <div className="text-center py-12">
        <p className="text-red-400">Opportunity not found</p>
        <Link href="/sales/opportunities" className="text-emerald-400 hover:text-emerald-300 mt-4 inline-block">
          Back to Opportunities
        </Link>
      </div>
    );
  }

  const currentStageIndex = stages?.findIndex((s: PipelineStage) => s.id === opportunity.stage_id) ?? -1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/sales/opportunities"
          className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-slate-400" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-foreground">{opportunity.name}</h1>
            <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${statusColors[opportunity.status] || statusColors.open}`}>
              {opportunity.status}
            </span>
          </div>
          <div className="flex items-center gap-4 mt-1 text-slate-400">
            {opportunity.customer_name && (
              <span className="flex items-center gap-1">
                <Building2 className="w-4 h-4" />
                {opportunity.customer_name}
              </span>
            )}
            {opportunity.stage_name && (
              <span className="flex items-center gap-1">
                <Target className="w-4 h-4" />
                {opportunity.stage_name}
              </span>
            )}
          </div>
        </div>

        {/* Actions */}
        {opportunity.status === 'open' && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowWonModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 rounded-lg transition-colors"
            >
              <CheckCircle className="w-4 h-4" />
              Mark Won
            </button>
            <button
              onClick={() => setShowLostModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded-lg transition-colors"
            >
              <XCircle className="w-4 h-4" />
              Mark Lost
            </button>
            <Link
              href={`/sales/opportunities/${oppId}/edit`}
              className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors text-slate-400"
            >
              <Edit className="w-4 h-4" />
            </Link>
          </div>
        )}
      </div>

      {/* Pipeline Progress */}
      {opportunity.status === 'open' && stages && (
        <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-lg font-medium text-foreground mb-4">Pipeline Progress</h2>
          <div className="flex items-center gap-2">
            {stages.filter((s: PipelineStage) => !s.is_won && !s.is_lost).map((stage: PipelineStage, index: number) => {
              const isActive = stage.id === opportunity.stage_id;
              const isPast = index < currentStageIndex;

              return (
                <button
                  key={stage.id}
                  onClick={() => handleMoveStage(stage.id)}
                  className={`flex-1 p-3 rounded-lg border transition-all ${
                    isActive
                      ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400'
                      : isPast
                      ? 'bg-slate-700/30 border-slate-600 text-foreground'
                      : 'bg-slate-800/50 border-slate-700/50 text-slate-400 hover:border-slate-600'
                  }`}
                >
                  <div className="text-sm font-medium">{stage.name}</div>
                  <div className="text-xs mt-1 opacity-70">{stage.probability}%</div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Deal Value Card */}
          <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
            <h2 className="text-lg font-medium text-foreground mb-4">Deal Value</h2>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <div className="text-sm text-slate-400">Deal Value</div>
                <div className="text-2xl font-semibold text-emerald-400 mt-1">
                  {formatCurrency(opportunity.deal_value || 0)}
                </div>
              </div>
              <div>
                <div className="text-sm text-slate-400">Probability</div>
                <div className="text-2xl font-semibold text-foreground mt-1">
                  {opportunity.probability || 0}%
                </div>
              </div>
              <div>
                <div className="text-sm text-slate-400">Weighted Value</div>
                <div className="text-2xl font-semibold text-cyan-400 mt-1">
                  {formatCurrency(opportunity.weighted_value || 0)}
                </div>
              </div>
            </div>
          </div>

          {/* Description */}
          {opportunity.description && (
            <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
              <h2 className="text-lg font-medium text-foreground mb-4">Description</h2>
              <p className="text-foreground-secondary whitespace-pre-wrap">{opportunity.description}</p>
            </div>
          )}

          {/* Lost Reason */}
          {opportunity.status === 'lost' && opportunity.lost_reason && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6">
              <h2 className="text-lg font-medium text-red-400 mb-4">Lost Reason</h2>
              <p className="text-foreground-secondary">{opportunity.lost_reason}</p>
              {opportunity.competitor && (
                <div className="mt-2">
                  <span className="text-sm text-slate-400">Competitor: </span>
                  <span className="text-foreground">{opportunity.competitor}</span>
                </div>
              )}
            </div>
          )}

          {/* Activity Timeline */}
          <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium text-foreground">Activity Timeline</h2>
              <Link
                href={`/sales/activities?opportunity_id=${oppId}`}
                className="text-sm text-emerald-400 hover:text-emerald-300"
              >
                View all
              </Link>
            </div>
            {activities?.items?.length === 0 ? (
              <p className="text-slate-400 text-center py-8">No activities yet</p>
            ) : (
              <div className="space-y-4">
                {activities?.items?.map((activity: Activity) => (
                  <div key={activity.id} className="flex items-start gap-3">
                    <div className="p-2 bg-slate-700/50 rounded-lg">
                      <MessageSquare className="w-4 h-4 text-slate-400" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-foreground font-medium">{activity.subject}</span>
                        <span className="text-xs text-slate-500">
                          {activity.created_at && formatDistanceToNow(activity.created_at)}
                        </span>
                      </div>
                      {activity.description && (
                        <p className="text-sm text-slate-400 mt-1 line-clamp-2">{activity.description}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Details Card */}
          <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
            <h2 className="text-lg font-medium text-foreground mb-4">Details</h2>
            <dl className="space-y-4">
              {opportunity.expected_close_date && (
                <div>
                  <dt className="text-xs text-slate-500">Expected Close</dt>
                  <dd className="text-foreground mt-1 flex items-center gap-1">
                    <Calendar className="w-4 h-4 text-slate-400" />
                    {formatDate(opportunity.expected_close_date, 'MMM d, yyyy')}
                  </dd>
                </div>
              )}
              {opportunity.actual_close_date && (
                <div>
                  <dt className="text-xs text-slate-500">Actual Close</dt>
                  <dd className="text-foreground mt-1">
                    {formatDate(opportunity.actual_close_date, 'MMM d, yyyy')}
                  </dd>
                </div>
              )}
              {opportunity.source && (
                <div>
                  <dt className="text-xs text-slate-500">Source</dt>
                  <dd className="text-foreground mt-1">{opportunity.source}</dd>
                </div>
              )}
              {opportunity.campaign && (
                <div>
                  <dt className="text-xs text-slate-500">Campaign</dt>
                  <dd className="text-foreground mt-1">{opportunity.campaign}</dd>
                </div>
              )}
              <div>
                <dt className="text-xs text-slate-500">Created</dt>
                <dd className="text-foreground mt-1">
                  {opportunity.created_at && formatDate(opportunity.created_at, 'MMM d, yyyy')}
                </dd>
              </div>
            </dl>
          </div>

          {/* Contacts */}
          {contacts && contacts.items?.length > 0 && (
            <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
              <h2 className="text-lg font-medium text-foreground mb-4">Contacts</h2>
              <div className="space-y-3">
                {contacts.items.map((contact: Contact) => (
                  <div key={contact.id} className="flex items-center gap-3 p-2 bg-slate-700/30 rounded-lg">
                    <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center text-foreground text-sm">
                      {contact.full_name?.charAt(0) || '?'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-foreground truncate">{contact.full_name}</div>
                      {contact.designation && (
                        <div className="text-xs text-slate-400 truncate">{contact.designation}</div>
                      )}
                    </div>
                    {contact.is_primary && (
                      <span className="text-xs text-emerald-400">Primary</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Related Documents */}
          <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
            <h2 className="text-lg font-medium text-foreground mb-4">Related</h2>
            <div className="space-y-2">
              {opportunity.quotation_id && (
                <Link
                  href={`/sales/quotations/${opportunity.quotation_id}`}
                  className="flex items-center justify-between p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-lg transition-colors"
                >
                  <span className="flex items-center gap-2 text-foreground">
                    <FileText className="w-4 h-4 text-amber-400" />
                    Quotation
                  </span>
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                </Link>
              )}
              {opportunity.sales_order_id && (
                <Link
                  href={`/sales/orders/${opportunity.sales_order_id}`}
                  className="flex items-center justify-between p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-lg transition-colors"
                >
                  <span className="flex items-center gap-2 text-foreground">
                    <ShoppingCart className="w-4 h-4 text-violet-400" />
                    Sales Order
                  </span>
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                </Link>
              )}
              {!opportunity.quotation_id && (
                <Link
                  href={`/sales/quotations/new?opportunity_id=${oppId}`}
                  className="flex items-center justify-between p-3 bg-emerald-500/10 hover:bg-emerald-500/20 rounded-lg transition-colors"
                >
                  <span className="flex items-center gap-2 text-emerald-400">
                    <FileText className="w-4 h-4" />
                    Create Quotation
                  </span>
                  <ChevronRight className="w-4 h-4" />
                </Link>
              )}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
            <h2 className="text-lg font-medium text-foreground mb-4">Quick Actions</h2>
            <div className="space-y-2">
              <Link
                href={`/sales/activities?opportunity_id=${oppId}&new=call`}
                className="flex items-center gap-3 p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-lg transition-colors"
              >
                <Phone className="w-4 h-4 text-emerald-400" />
                <span className="text-foreground">Log Call</span>
              </Link>
              <Link
                href={`/sales/activities?opportunity_id=${oppId}&new=meeting`}
                className="flex items-center gap-3 p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-lg transition-colors"
              >
                <Calendar className="w-4 h-4 text-blue-400" />
                <span className="text-foreground">Schedule Meeting</span>
              </Link>
              <Link
                href={`/sales/activities?opportunity_id=${oppId}&new=email`}
                className="flex items-center gap-3 p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-lg transition-colors"
              >
                <Mail className="w-4 h-4 text-amber-400" />
                <span className="text-foreground">Send Email</span>
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Mark Won Modal */}
      {showWonModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-foreground mb-4">Mark as Won</h3>
            <div className="mb-4">
              <label className="block text-sm text-slate-400 mb-2">Close Date</label>
              <input
                type="date"
                value={actualCloseDate}
                onChange={(e) => setActualCloseDate(e.target.value)}
                className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowWonModal(false)}
                className="px-4 py-2 text-slate-400 hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleMarkWon}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-foreground rounded-lg transition-colors"
              >
                Mark as Won
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Mark Lost Modal */}
      {showLostModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-foreground mb-4">Mark as Lost</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-2">Lost Reason</label>
                <textarea
                  value={lostReason}
                  onChange={(e) => setLostReason(e.target.value)}
                  placeholder="Why was this opportunity lost?"
                  className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-red-500/50"
                  rows={3}
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-2">Competitor</label>
                <input
                  type="text"
                  value={competitor}
                  onChange={(e) => setCompetitor(e.target.value)}
                  placeholder="Who did we lose to?"
                  className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-red-500/50"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowLostModal(false)}
                className="px-4 py-2 text-slate-400 hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleMarkLost}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-foreground rounded-lg transition-colors"
              >
                Mark as Lost
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
