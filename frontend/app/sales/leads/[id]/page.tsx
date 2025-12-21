'use client';

import { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Phone,
  Mail,
  Building2,
  MapPin,
  Globe,
  Calendar,
  CheckCircle,
  XCircle,
  ArrowRight,
  Edit,
  Trash2,
  MessageSquare,
  Clock,
  User,
  DollarSign,
} from 'lucide-react';
import { useLead, useLeadMutations, useLeadContacts, useActivityTimeline } from '@/hooks/useApi';
import { formatDistanceToNow, formatDate } from '@/lib/date';
import type { Activity, Contact } from '@/lib/api';

const statusColors: Record<string, string> = {
  new: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  contacted: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  qualified: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  unqualified: 'bg-red-500/20 text-red-400 border-red-500/30',
  converted: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
};

export default function LeadDetailPage() {
  const router = useRouter();
  const params = useParams();
  const leadId = params.id as string;

  const { data: lead, isLoading, error } = useLead(leadId);
  const { data: contacts } = useLeadContacts(lead?.id);
  const { data: activities } = useActivityTimeline({ lead_id: lead?.id, limit: 10 });
  const { qualifyLead, disqualifyLead, convertLead } = useLeadMutations();

  const [showConvertModal, setShowConvertModal] = useState(false);
  const [showDisqualifyModal, setShowDisqualifyModal] = useState(false);
  const [disqualifyReason, setDisqualifyReason] = useState('');
  const [convertData, setConvertData] = useState({
    create_opportunity: true,
    opportunity_name: '',
    deal_value: 0,
  });

  const handleQualify = async () => {
    try {
      await qualifyLead(leadId);
    } catch (error) {
      console.error('Failed to qualify lead:', error);
    }
  };

  const handleDisqualify = async () => {
    try {
      await disqualifyLead(leadId, disqualifyReason);
      setShowDisqualifyModal(false);
    } catch (error) {
      console.error('Failed to disqualify lead:', error);
    }
  };

  const handleConvert = async () => {
    try {
      await convertLead(leadId, {
        create_opportunity: convertData.create_opportunity,
        opportunity_name: convertData.opportunity_name || `${lead?.company_name || lead?.lead_name} - Opportunity`,
        deal_value: convertData.deal_value,
      });
      setShowConvertModal(false);
      router.push('/sales/opportunities');
    } catch (error) {
      console.error('Failed to convert lead:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-400" />
      </div>
    );
  }

  if (error || !lead) {
    return (
      <div className="text-center py-12">
        <p className="text-red-400">Lead not found</p>
        <Link href="/sales/leads" className="text-emerald-400 hover:text-emerald-300 mt-4 inline-block">
          Back to Leads
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/sales/leads"
          className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-slate-400" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-foreground">{lead.lead_name || 'Unnamed Lead'}</h1>
            <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${statusColors[lead.status] || statusColors.new}`}>
              {lead.status}
            </span>
          </div>
          {lead.company_name && (
            <p className="text-slate-400 mt-1 flex items-center gap-1">
              <Building2 className="w-4 h-4" />
              {lead.company_name}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {(lead.status === 'new' || lead.status === 'contacted') && (
            <>
              <button
                onClick={handleQualify}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 rounded-lg transition-colors"
              >
                <CheckCircle className="w-4 h-4" />
                Qualify
              </button>
              <button
                onClick={() => setShowDisqualifyModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded-lg transition-colors"
              >
                <XCircle className="w-4 h-4" />
                Disqualify
              </button>
            </>
          )}
          {lead.status === 'qualified' && (
            <button
              onClick={() => setShowConvertModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-foreground rounded-lg transition-colors"
            >
              <ArrowRight className="w-4 h-4" />
              Convert to Customer
            </button>
          )}
          <Link
            href={`/sales/leads/${leadId}/edit`}
            className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors text-slate-400"
          >
            <Edit className="w-4 h-4" />
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Contact Info */}
          <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
            <h2 className="text-lg font-medium text-foreground mb-4">Contact Information</h2>
            <div className="grid grid-cols-2 gap-4">
              {lead.email_id && (
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-slate-700/50 rounded-lg">
                    <Mail className="w-4 h-4 text-slate-400" />
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Email</div>
                    <a href={`mailto:${lead.email_id}`} className="text-foreground hover:text-emerald-400">
                      {lead.email_id}
                    </a>
                  </div>
                </div>
              )}
              {lead.phone && (
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-slate-700/50 rounded-lg">
                    <Phone className="w-4 h-4 text-slate-400" />
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Phone</div>
                    <a href={`tel:${lead.phone}`} className="text-foreground hover:text-emerald-400">
                      {lead.phone}
                    </a>
                  </div>
                </div>
              )}
              {lead.mobile_no && (
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-slate-700/50 rounded-lg">
                    <Phone className="w-4 h-4 text-slate-400" />
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Mobile</div>
                    <a href={`tel:${lead.mobile_no}`} className="text-foreground hover:text-emerald-400">
                      {lead.mobile_no}
                    </a>
                  </div>
                </div>
              )}
              {lead.website && (
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-slate-700/50 rounded-lg">
                    <Globe className="w-4 h-4 text-slate-400" />
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Website</div>
                    <a href={lead.website} target="_blank" rel="noopener noreferrer" className="text-foreground hover:text-emerald-400">
                      {lead.website}
                    </a>
                  </div>
                </div>
              )}
            </div>

            {(lead.address_line1 || lead.city || lead.state) && (
              <div className="mt-4 pt-4 border-t border-slate-700/50">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-slate-700/50 rounded-lg">
                    <MapPin className="w-4 h-4 text-slate-400" />
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Address</div>
                    <div className="text-foreground">
                      {lead.address_line1 && <div>{lead.address_line1}</div>}
                      {lead.address_line2 && <div>{lead.address_line2}</div>}
                      <div>
                        {[lead.city, lead.state, lead.postal_code].filter(Boolean).join(', ')}
                      </div>
                      {lead.country && <div>{lead.country}</div>}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Notes */}
          {lead.notes && (
            <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
              <h2 className="text-lg font-medium text-foreground mb-4">Notes</h2>
              <p className="text-foreground-secondary whitespace-pre-wrap">{lead.notes}</p>
            </div>
          )}

          {/* Activity Timeline */}
          <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium text-foreground">Activity Timeline</h2>
              <Link
                href={`/sales/activities?lead_id=${leadId}`}
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
                          {activity.created_at && formatDistanceToNow(new Date(activity.created_at))}
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
              {lead.source && (
                <div>
                  <dt className="text-xs text-slate-500">Source</dt>
                  <dd className="text-foreground mt-1">{lead.source}</dd>
                </div>
              )}
              {lead.campaign && (
                <div>
                  <dt className="text-xs text-slate-500">Campaign</dt>
                  <dd className="text-foreground mt-1">{lead.campaign}</dd>
                </div>
              )}
              {lead.industry && (
                <div>
                  <dt className="text-xs text-slate-500">Industry</dt>
                  <dd className="text-foreground mt-1">{lead.industry}</dd>
                </div>
              )}
              {lead.territory && (
                <div>
                  <dt className="text-xs text-slate-500">Territory</dt>
                  <dd className="text-foreground mt-1">{lead.territory}</dd>
                </div>
              )}
              <div>
                <dt className="text-xs text-slate-500">Created</dt>
                <dd className="text-foreground mt-1">
                    {lead.created_at && formatDate(new Date(lead.created_at), 'MMM d, yyyy')}
                </dd>
              </div>
              {lead.last_synced_at && (
                <div>
                  <dt className="text-xs text-slate-500">Last Synced</dt>
                  <dd className="text-foreground mt-1">
                    {formatDistanceToNow(new Date(lead.last_synced_at))}
                  </dd>
                </div>
              )}
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

          {/* Quick Actions */}
          <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
            <h2 className="text-lg font-medium text-foreground mb-4">Quick Actions</h2>
            <div className="space-y-2">
              <Link
                href={`/sales/activities?lead_id=${leadId}&new=call`}
                className="flex items-center gap-3 p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-lg transition-colors"
              >
                <Phone className="w-4 h-4 text-emerald-400" />
                <span className="text-foreground">Log Call</span>
              </Link>
              <Link
                href={`/sales/activities?lead_id=${leadId}&new=meeting`}
                className="flex items-center gap-3 p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-lg transition-colors"
              >
                <Calendar className="w-4 h-4 text-blue-400" />
                <span className="text-foreground">Schedule Meeting</span>
              </Link>
              <Link
                href={`/sales/activities?lead_id=${leadId}&new=email`}
                className="flex items-center gap-3 p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-lg transition-colors"
              >
                <Mail className="w-4 h-4 text-amber-400" />
                <span className="text-foreground">Send Email</span>
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Disqualify Modal */}
      {showDisqualifyModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-foreground mb-4">Disqualify Lead</h3>
            <div className="mb-4">
              <label className="block text-sm text-slate-400 mb-2">Reason</label>
              <textarea
                value={disqualifyReason}
                onChange={(e) => setDisqualifyReason(e.target.value)}
                placeholder="Why is this lead being disqualified?"
                className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-red-500/50"
                rows={3}
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDisqualifyModal(false)}
                className="px-4 py-2 text-slate-400 hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDisqualify}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-foreground rounded-lg transition-colors"
              >
                Disqualify
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Convert Modal */}
      {showConvertModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-foreground mb-4">Convert to Customer</h3>
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="createOpportunity"
                  checked={convertData.create_opportunity}
                  onChange={(e) => setConvertData(prev => ({ ...prev, create_opportunity: e.target.checked }))}
                  className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-emerald-500 focus:ring-emerald-500/50"
                />
                <label htmlFor="createOpportunity" className="text-foreground">
                  Create opportunity
                </label>
              </div>

              {convertData.create_opportunity && (
                <>
                  <div>
                    <label className="block text-sm text-slate-400 mb-2">Opportunity Name</label>
                    <input
                      type="text"
                      value={convertData.opportunity_name}
                      onChange={(e) => setConvertData(prev => ({ ...prev, opportunity_name: e.target.value }))}
                      placeholder={`${lead?.company_name || lead?.lead_name} - Opportunity`}
                      className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-2">Deal Value</label>
                    <div className="relative">
                      <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                      <input
                        type="number"
                        value={convertData.deal_value}
                        onChange={(e) => setConvertData(prev => ({ ...prev, deal_value: parseFloat(e.target.value) || 0 }))}
                        placeholder="0.00"
                        className="w-full pl-10 pr-4 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                      />
                    </div>
                  </div>
                </>
              )}
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowConvertModal(false)}
                className="px-4 py-2 text-slate-400 hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConvert}
                className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-foreground rounded-lg transition-colors"
              >
                Convert
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
