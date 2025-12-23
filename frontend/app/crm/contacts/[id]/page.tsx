'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useUnifiedContact, useUnifiedContactMutations, type UnifiedContact } from '@/hooks/useApi';
import type { Contact as CRMContact } from '@/lib/api';
import { cn } from '@/lib/utils';
import { formatCurrency, formatDate, formatDateTime } from '@/lib/formatters';
import {
  Mail,
  Phone,
  MapPin,
  Globe,
  Linkedin,
  Tag,
  ArrowLeft,
  Edit,
  Trash2,
  UserCheck,
  AlertCircle,
  CheckCircle,
} from 'lucide-react';
import { ErrorDisplay } from '@/components/insights/shared';
import { Button, LoadingState } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

const contactTypeColors: Record<string, string> = {
  lead: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  prospect: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  customer: 'bg-green-500/20 text-green-400 border-green-500/30',
  churned: 'bg-red-500/20 text-red-400 border-red-500/30',
  person: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

const statusColors: Record<string, string> = {
  active: 'bg-green-500/20 text-green-400',
  inactive: 'bg-gray-500/20 text-gray-400',
  suspended: 'bg-red-500/20 text-red-400',
  do_not_contact: 'bg-red-500/20 text-red-400',
};

type ContactType = 'lead' | 'prospect' | 'customer' | 'person' | 'churned';
type ContactStatus = 'active' | 'inactive' | 'suspended' | 'do_not_contact';

const qualificationColors: Record<string, string> = {
  unqualified: 'bg-gray-500',
  cold: 'bg-blue-500',
  warm: 'bg-amber-500',
  hot: 'bg-orange-500',
  qualified: 'bg-green-500',
};

export default function ContactDetailPage() {
  const { isLoading: authLoading, missingScope } = useRequireScope('crm:read');
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const canFetch = !authLoading && !missingScope;

  const { data: contact, isLoading, error, mutate } = useUnifiedContact(id, { isPaused: () => !canFetch }) as {
    data?: CRMContact;
    isLoading: boolean;
    error?: unknown;
    mutate: () => Promise<any>;
  };
  const mutations = useUnifiedContactMutations();
  const contactType = (contact?.contact_type as ContactType | undefined) || 'lead';
  const contactStatus = (contact?.status as ContactStatus | undefined) || 'active';

  const handleQualify = async (qualification: string) => {
    try {
      await mutations.qualifyLead(id, qualification);
      mutate();
    } catch (err) {
      console.error('Failed to qualify lead:', err);
    }
  };

  const handleConvertToCustomer = async () => {
    try {
      await mutations.convertToCustomer(id);
      mutate();
    } catch (err) {
      console.error('Failed to convert to customer:', err);
    }
  };

  const handleDelete = async () => {
    try {
      await mutations.deleteContact(id, false);
      router.push('/crm');
    } catch (err) {
      console.error('Failed to delete contact:', err);
    }
  };

  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the crm:read permission to view contact details."
        backHref="/crm"
        backLabel="Back to CRM"
      />
    );
  }

  if (isLoading) {
    return <LoadingState />;
  }

  if (!contact) {
    return (
      <div className="space-y-6">
        {Boolean(error) && (
          <ErrorDisplay
            message="Failed to load contact"
            error={error as Error}
            onRetry={() => mutate()}
          />
        )}
        <div className="flex flex-col items-center justify-center py-12">
          <AlertCircle className="w-12 h-12 text-slate-muted mb-4" />
          <p className="text-foreground text-lg">Contact not found</p>
          <Link href="/crm" className="mt-4 text-teal-electric hover:text-teal-glow">
            Back to CRM
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {Boolean(error) && (
        <ErrorDisplay
          message="Failed to load contact"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/crm"
            className="p-2 hover:bg-slate-elevated rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-slate-muted" />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-foreground">{contact.name}</h1>
              <span className={cn(
                'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border',
                contactTypeColors[contactType] || contactTypeColors.lead
              )}>
                {contactType}
              </span>
              <span className={cn(
                'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium',
                statusColors[contactStatus] || statusColors.active
              )}>
                {contactStatus}
              </span>
            </div>
            {contact.company_name && contact.company_name !== contact.name && (
              <p className="text-slate-muted">{contact.company_name}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href={`/crm/contacts/${id}/edit`}
            className="flex items-center gap-2 px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground hover:bg-slate-border transition-colors"
          >
            <Edit className="w-4 h-4" />
            Edit
          </Link>
          <Button
            onClick={() => setShowDeleteModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 hover:bg-red-500/30 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Delete
          </Button>
        </div>
      </div>

      {/* Quick Actions for Leads */}
      {(contactType === 'lead' || contactType === 'prospect') && (
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-foreground font-medium">Lead Qualification</p>
              <div className="flex items-center gap-2 mt-2">
                {['cold', 'warm', 'hot', 'qualified'].map((qual) => (
                  <Button
                    key={qual}
                    onClick={() => handleQualify(qual)}
                    className={cn(
                      'px-3 py-1 rounded-full text-xs font-medium transition-colors',
                      contact.lead_qualification === qual
                        ? qualificationColors[qual] + ' text-foreground'
                        : 'bg-slate-elevated text-slate-muted hover:bg-slate-border'
                    )}
                  >
                    {qual}
                  </Button>
                ))}
              </div>
            </div>
            <Button
              onClick={handleConvertToCustomer}
              className="flex items-center gap-2 px-4 py-2 bg-green-500/20 border border-green-500/30 rounded-lg text-green-400 hover:bg-green-500/30 transition-colors"
            >
              <UserCheck className="w-4 h-4" />
              Convert to Customer
            </Button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Contact Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Contact Details */}
          <div className="bg-slate-card rounded-xl border border-slate-border p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Contact Details</h3>
            <div className="grid grid-cols-2 gap-4">
              {contact.email && (
                <div className="flex items-start gap-3">
                  <Mail className="w-5 h-5 text-slate-muted mt-0.5" />
                  <div>
                    <p className="text-sm text-slate-muted">Email</p>
                    <a href={`mailto:${contact.email}`} className="text-foreground hover:text-teal-electric">
                      {contact.email}
                    </a>
                  </div>
                </div>
              )}
              {contact.phone && (
                <div className="flex items-start gap-3">
                  <Phone className="w-5 h-5 text-slate-muted mt-0.5" />
                  <div>
                    <p className="text-sm text-slate-muted">Phone</p>
                    <a href={`tel:${contact.phone}`} className="text-foreground hover:text-teal-electric">
                      {contact.phone}
                    </a>
                  </div>
                </div>
              )}
              {contact.mobile && (
                <div className="flex items-start gap-3">
                  <Phone className="w-5 h-5 text-slate-muted mt-0.5" />
                  <div>
                    <p className="text-sm text-slate-muted">Mobile</p>
                    <a href={`tel:${contact.mobile}`} className="text-foreground hover:text-teal-electric">
                      {contact.mobile}
                    </a>
                  </div>
                </div>
              )}
              {contact.website && (
                <div className="flex items-start gap-3">
                  <Globe className="w-5 h-5 text-slate-muted mt-0.5" />
                  <div>
                    <p className="text-sm text-slate-muted">Website</p>
                    <a href={contact.website} target="_blank" rel="noopener noreferrer" className="text-foreground hover:text-teal-electric">
                      {contact.website}
                    </a>
                  </div>
                </div>
              )}
              {contact.linkedin_url && (
                <div className="flex items-start gap-3">
                  <Linkedin className="w-5 h-5 text-slate-muted mt-0.5" />
                  <div>
                    <p className="text-sm text-slate-muted">LinkedIn</p>
                    <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-foreground hover:text-teal-electric">
                      View Profile
                    </a>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Address */}
          {(contact.address_line1 || contact.city || contact.state) && (
            <div className="bg-slate-card rounded-xl border border-slate-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Address</h3>
              <div className="flex items-start gap-3">
                <MapPin className="w-5 h-5 text-slate-muted mt-0.5" />
                <div className="text-foreground">
                  {contact.address_line1 && <p>{contact.address_line1}</p>}
                  {contact.address_line2 && <p>{contact.address_line2}</p>}
                  <p>
                    {[contact.city, contact.state, contact.postal_code].filter(Boolean).join(', ')}
                  </p>
                  {contact.country && <p>{contact.country}</p>}
                </div>
              </div>
            </div>
          )}

          {/* Financial Info (for customers) */}
          {contactType === 'customer' && (
            <div className="bg-slate-card rounded-xl border border-slate-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Financial</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-sm text-slate-muted">MRR</p>
                  <p className="text-xl font-bold text-foreground">{formatCurrency(contact.mrr || 0)}</p>
                </div>
                <div>
                  <p className="text-sm text-slate-muted">Total Revenue</p>
                  <p className="text-xl font-bold text-foreground">{formatCurrency(contact.total_revenue || 0)}</p>
                </div>
                <div>
                  <p className="text-sm text-slate-muted">Outstanding</p>
                  <p className={cn(
                    'text-xl font-bold',
                    (contact.outstanding_balance || 0) > 0 ? 'text-red-400' : 'text-foreground'
                  )}>
                    {formatCurrency(contact.outstanding_balance || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-muted">Credit Limit</p>
                  <p className="text-xl font-bold text-foreground">{formatCurrency(contact.credit_limit || 0)}</p>
                </div>
              </div>
              {contact.account_number && (
                <div className="mt-4 pt-4 border-t border-slate-border">
                  <p className="text-sm text-slate-muted">Account Number</p>
                  <p className="text-foreground font-mono">{contact.account_number}</p>
                </div>
              )}
            </div>
          )}

          {/* Notes */}
          {contact.notes && (
            <div className="bg-slate-card rounded-xl border border-slate-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Notes</h3>
              <div className="prose prose-invert max-w-none">
                <pre className="whitespace-pre-wrap text-sm text-slate-muted font-sans">{contact.notes}</pre>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Classification */}
          <div className="bg-slate-card rounded-xl border border-slate-border p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Classification</h3>
            <div className="space-y-3">
              <div>
                <p className="text-sm text-slate-muted">Category</p>
                <p className="text-foreground capitalize">{contact.category}</p>
              </div>
              {contact.territory && (
                <div>
                  <p className="text-sm text-slate-muted">Territory</p>
                  <p className="text-foreground">{contact.territory}</p>
                </div>
              )}
              {contact.source && (
                <div>
                  <p className="text-sm text-slate-muted">Source</p>
                  <p className="text-foreground">{contact.source}</p>
                </div>
              )}
              {contact.lead_score !== null && contact.lead_score !== undefined && (
                <div>
                  <p className="text-sm text-slate-muted">Lead Score</p>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-slate-elevated rounded-full overflow-hidden">
                      <div
                        className="h-full bg-teal-electric"
                        style={{ width: `${contact.lead_score}%` }}
                      />
                    </div>
                    <span className="text-foreground">{contact.lead_score}</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Tags */}
          {contact.tags && contact.tags.length > 0 && (
            <div className="bg-slate-card rounded-xl border border-slate-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {contact.tags.map((tag: string) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 px-3 py-1 bg-slate-elevated rounded-full text-sm text-slate-muted"
                  >
                    <Tag className="w-3 h-3" />
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Lifecycle Dates */}
          <div className="bg-slate-card rounded-xl border border-slate-border p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Timeline</h3>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-muted">Created</span>
                <span className="text-foreground">{formatDate(contact.created_at)}</span>
              </div>
              {contact.first_contact_date && (
                <div className="flex items-center justify-between">
                  <span className="text-slate-muted">First Contact</span>
                  <span className="text-foreground">{formatDate(contact.first_contact_date)}</span>
                </div>
              )}
              {contact.qualified_date && (
                <div className="flex items-center justify-between">
                  <span className="text-slate-muted">Qualified</span>
                  <span className="text-foreground">{formatDate(contact.qualified_date)}</span>
                </div>
              )}
              {contact.conversion_date && (
                <div className="flex items-center justify-between">
                  <span className="text-slate-muted">Converted</span>
                  <span className="text-foreground">{formatDate(contact.conversion_date)}</span>
                </div>
              )}
              {contact.last_contact_date && (
                <div className="flex items-center justify-between">
                  <span className="text-slate-muted">Last Contact</span>
                  <span className="text-foreground">{formatDateTime(contact.last_contact_date)}</span>
                </div>
              )}
            </div>
          </div>

          {/* Stats */}
          <div className="bg-slate-card rounded-xl border border-slate-border p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Activity Stats</h3>
            <div className="grid grid-cols-2 gap-4 text-center">
              <div className="p-3 bg-slate-elevated rounded-lg">
                <p className="text-2xl font-bold text-foreground">{contact.total_conversations}</p>
                <p className="text-xs text-slate-muted">Conversations</p>
              </div>
              <div className="p-3 bg-slate-elevated rounded-lg">
                <p className="text-2xl font-bold text-foreground">{contact.total_tickets}</p>
                <p className="text-xs text-slate-muted">Tickets</p>
              </div>
              <div className="p-3 bg-slate-elevated rounded-lg">
                <p className="text-2xl font-bold text-foreground">{contact.total_orders}</p>
                <p className="text-xs text-slate-muted">Orders</p>
              </div>
              <div className="p-3 bg-slate-elevated rounded-lg">
                <p className="text-2xl font-bold text-foreground">{contact.total_invoices}</p>
                <p className="text-xs text-slate-muted">Invoices</p>
              </div>
            </div>
          </div>

          {/* Communication Preferences */}
          <div className="bg-slate-card rounded-xl border border-slate-border p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Communication</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-muted">Email</span>
                {contact.email_opt_in ? (
                  <CheckCircle className="w-4 h-4 text-green-400" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-red-400" />
                )}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-muted">SMS</span>
                {contact.sms_opt_in ? (
                  <CheckCircle className="w-4 h-4 text-green-400" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-red-400" />
                )}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-muted">WhatsApp</span>
                {contact.whatsapp_opt_in ? (
                  <CheckCircle className="w-4 h-4 text-green-400" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-red-400" />
                )}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-muted">Phone</span>
                {contact.phone_opt_in ? (
                  <CheckCircle className="w-4 h-4 text-green-400" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-red-400" />
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Delete Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-card border border-slate-border rounded-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-foreground mb-2">Delete Contact</h3>
            <p className="text-slate-muted mb-4">
              Are you sure you want to delete this contact? This action will deactivate the contact.
            </p>
            <div className="flex justify-end gap-3">
              <Button
                onClick={() => setShowDeleteModal(false)}
                className="px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground hover:bg-slate-border transition-colors"
              >
                Cancel
              </Button>
              <Button
                onClick={handleDelete}
                className="px-4 py-2 bg-red-500 text-foreground rounded-lg hover:bg-red-600 transition-colors"
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
