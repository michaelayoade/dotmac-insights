'use client';

import { useState, useMemo } from 'react';
import {
  Users,
  Plus,
  Building2,
  MessageSquare,
  Trash2,
  Edit,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useInboxContacts,
  useInboxContactMutations,
  useInboxCompanies,
} from '@/hooks/useInbox';
import type { InboxContact } from '@/lib/inbox.types';
import {
  PageHeader,
  EmptyState,
  ErrorState,
  SearchInput,
  Select,
  StatGrid,
  Button,
} from '@/components/ui';
import { StatCard } from '@/components/StatCard';

function formatTimeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Never';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function TableSkeleton() {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-border">
            <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Contact</th>
            <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted hidden md:table-cell">Company</th>
            <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted hidden lg:table-cell">Tags</th>
            <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Conversations</th>
            <th className="text-left px-4 py-3 text-sm font-medium text-slate-muted hidden md:table-cell">Last Contact</th>
            <th className="text-right px-4 py-3 text-sm font-medium text-slate-muted">Actions</th>
          </tr>
        </thead>
        <tbody>
          {[1, 2, 3, 4, 5].map((i) => (
            <tr key={i} className="border-b border-slate-border/50 animate-pulse">
              <td className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-slate-elevated" />
                  <div>
                    <div className="h-4 w-24 bg-slate-elevated rounded mb-1" />
                    <div className="h-3 w-32 bg-slate-elevated rounded" />
                  </div>
                </div>
              </td>
              <td className="px-4 py-3 hidden md:table-cell">
                <div className="h-4 w-20 bg-slate-elevated rounded" />
              </td>
              <td className="px-4 py-3 hidden lg:table-cell">
                <div className="h-4 w-16 bg-slate-elevated rounded" />
              </td>
              <td className="px-4 py-3">
                <div className="h-4 w-8 bg-slate-elevated rounded" />
              </td>
              <td className="px-4 py-3 hidden md:table-cell">
                <div className="h-4 w-16 bg-slate-elevated rounded" />
              </td>
              <td className="px-4 py-3">
                <div className="h-4 w-12 bg-slate-elevated rounded ml-auto" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ContactsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [tagFilter, setTagFilter] = useState('all');
  const [companyFilter, setCompanyFilter] = useState('');

  const listParams = useMemo(() => ({
    search: searchQuery || undefined,
    company: companyFilter || undefined,
    tag: tagFilter !== 'all' ? tagFilter : undefined,
    sort_by: 'last_contact_at',
    sort_order: 'desc' as const,
    limit: 50,
  }), [searchQuery, companyFilter, tagFilter]);

  const {
    data: contactsData,
    error: contactsError,
    isLoading: contactsLoading,
    mutate: refreshContacts,
  } = useInboxContacts(listParams);

  const {
    data: companiesData,
    isLoading: companiesLoading,
  } = useInboxCompanies({ limit: 100 });

  const mutations = useInboxContactMutations();

  const contacts = contactsData?.data;
  const companies = companiesData?.data;

  // Get all unique tags from contacts
  const allTags = useMemo(() => {
    const tags = new Set<string>();
    (contacts ?? []).forEach((c) => {
      (c.tags || []).forEach((t) => tags.add(t));
    });
    return Array.from(tags).sort();
  }, [contacts]);

  // Count stats
  const totalContacts = contactsData?.total || 0;
  const vipCount = (contacts ?? []).filter((c) => (c.tags || []).includes('vip')).length;
  const totalConversations = (contacts ?? []).reduce((sum, c) => sum + (c.total_conversations || 0), 0);

  const handleDeleteContact = async (contact: InboxContact) => {
    if (!confirm(`Are you sure you want to delete "${contact.name}"?`)) return;
    try {
      await mutations.deleteContact(contact.id);
    } catch (error) {
      console.error('Failed to delete contact:', error);
    }
  };

  const tagOptions = [
    { value: 'all', label: 'All Tags' },
    ...allTags.map((tag) => ({ value: tag, label: tag })),
  ];

  const companyOptions = [
    { value: '', label: 'All Companies' },
    ...(companies ?? []).map((c) => ({ value: c.company, label: `${c.company} (${c.contact_count})` })),
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Contacts"
        subtitle="Unified contact directory"
        icon={Users}
        iconClassName="bg-emerald-500/10 border border-emerald-500/30"
        actions={
          <Button icon={Plus}>Add Contact</Button>
        }
      />

      {/* Search and filters */}
      <div className="flex flex-col md:flex-row gap-3">
        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Search contacts..."
          className="flex-1"
        />
        <Select
          value={tagFilter}
          onChange={setTagFilter}
          options={tagOptions}
          aria-label="Filter by tag"
        />
        <Select
          value={companyFilter}
          onChange={setCompanyFilter}
          options={companyOptions}
          aria-label="Filter by company"
        />
      </div>

      {/* Stats */}
      <StatGrid columns={4}>
        <StatCard
          title="Total Contacts"
          value={totalContacts}
          loading={contactsLoading}
          icon={Users}
        />
        <StatCard
          title="Companies"
          value={(companies ?? []).length}
          loading={companiesLoading}
          icon={Building2}
          variant="success"
        />
        <StatCard
          title="VIP Contacts"
          value={vipCount}
          loading={contactsLoading}
          variant="warning"
        />
        <StatCard
          title="Conversations"
          value={totalConversations}
          loading={contactsLoading}
          variant="success"
        />
      </StatGrid>

      {/* Contact list */}
      {contactsLoading ? (
        <TableSkeleton />
      ) : contactsError ? (
        <ErrorState message="Failed to load contacts" onRetry={() => refreshContacts()} />
      ) : (contacts ?? []).length === 0 ? (
        <EmptyState
          icon={Users}
          title="No contacts found"
          description="Add your first contact to get started"
          action={{ label: 'Add Contact', icon: Plus }}
        />
      ) : (
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <table className="w-full" role="table">
            <thead>
              <tr className="border-b border-slate-border">
                <th scope="col" className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Contact</th>
                <th scope="col" className="text-left px-4 py-3 text-sm font-medium text-slate-muted hidden md:table-cell">Company</th>
                <th scope="col" className="text-left px-4 py-3 text-sm font-medium text-slate-muted hidden lg:table-cell">Tags</th>
                <th scope="col" className="text-left px-4 py-3 text-sm font-medium text-slate-muted">Conversations</th>
                <th scope="col" className="text-left px-4 py-3 text-sm font-medium text-slate-muted hidden md:table-cell">Last Contact</th>
                <th scope="col" className="text-right px-4 py-3 text-sm font-medium text-slate-muted">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(contacts ?? []).map((contact) => (
                <tr key={contact.id} className="border-b border-slate-border/50 hover:bg-slate-elevated/30 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-slate-elevated flex items-center justify-center text-foreground font-semibold">
                        {contact.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-foreground font-medium">{contact.name}</p>
                        <p className="text-sm text-slate-muted">{contact.email || contact.phone || '-'}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    {contact.company ? (
                      <span className="flex items-center gap-1 text-slate-200">
                        <Building2 className="w-3 h-3 text-slate-muted" />
                        {contact.company}
                      </span>
                    ) : (
                      <span className="text-slate-muted">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 hidden lg:table-cell">
                    <div className="flex items-center gap-1 flex-wrap">
                      {(contact.tags || []).length > 0 ? (
                        (contact.tags || []).slice(0, 3).map((tag) => (
                          <span key={tag} className="px-2 py-0.5 rounded bg-slate-elevated text-xs text-slate-muted">
                            {tag}
                          </span>
                        ))
                      ) : (
                        <span className="text-slate-muted">-</span>
                      )}
                      {(contact.tags || []).length > 3 && (
                        <span className="text-xs text-slate-muted">+{(contact.tags || []).length - 3}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-foreground font-medium">{contact.total_conversations || 0}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-muted text-sm hidden md:table-cell">
                    {formatTimeAgo(contact.last_contact_at)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
                        title="Send message"
                        aria-label={`Send message to ${contact.name}`}
                      >
                        <MessageSquare className="w-4 h-4" />
                      </button>
                      <button
                        className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
                        title="Edit contact"
                        aria-label={`Edit ${contact.name}`}
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteContact(contact)}
                        className="p-2 text-slate-muted hover:text-rose-400 hover:bg-slate-elevated rounded-lg transition-colors"
                        title="Delete contact"
                        aria-label={`Delete ${contact.name}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination info */}
          {contactsData && contactsData.total > (contacts ?? []).length && (
            <div className="px-4 py-3 border-t border-slate-border text-sm text-slate-muted">
              Showing {(contacts ?? []).length} of {contactsData.total} contacts
            </div>
          )}
        </div>
      )}
    </div>
  );
}
