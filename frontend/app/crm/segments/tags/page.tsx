'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import {
  Tag,
  Users,
  Plus,
  Hash,
} from 'lucide-react';
import useSWR from 'swr';
import { apiFetch, type UnifiedContact } from '@/hooks/useApi';
import { ErrorDisplay } from '@/components/insights/shared';
import { LoadingState, Button, FilterInput, PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

interface TagCount {
  tag: string;
  count: number;
}

interface TagsAnalytics {
  total_unique_tags: number;
  total_contacts: number;
  total_tagged_contacts: number;
  total_tag_assignments: number;
  avg_tags_per_contact: number;
  tags: TagCount[];
}

interface ContactsListResponse {
  data?: UnifiedContact[];
  items?: UnifiedContact[];
  total?: number;
}

const tagColors = [
  'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  'bg-violet-500/20 text-violet-400 border-violet-500/30',
  'bg-amber-500/20 text-amber-400 border-amber-500/30',
  'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  'bg-rose-500/20 text-rose-400 border-rose-500/30',
  'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'bg-orange-500/20 text-orange-400 border-orange-500/30',
  'bg-purple-500/20 text-purple-400 border-purple-500/30',
];

export default function CRMTagsPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('crm:read');
  const [search, setSearch] = useState('');
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const canFetch = !authLoading && !missingScope;

  // Fetch tags analytics from backend
  const { data: analytics, isLoading: analyticsLoading, error: analyticsError, mutate: mutateAnalytics } = useSWR<TagsAnalytics>(
    canFetch ? '/contacts/analytics/tags?limit=100' : null,
    apiFetch
  );

  // Fetch contacts only when a tag is selected
  const {
    data: contactsResponse,
    isLoading: contactsLoading,
    error: contactsError,
    mutate: mutateContacts,
  } = useSWR<ContactsListResponse>(
    canFetch && selectedTag ? `/contacts?tag=${encodeURIComponent(selectedTag)}&page=1&page_size=100` : null,
    apiFetch
  );

  const contacts = contactsResponse?.data || contactsResponse?.items || [];

  // Use analytics data for tag counts
  const tagCounts = useMemo(() => analytics?.tags || [], [analytics?.tags]);

  // Filter tags by search
  const filteredTags = useMemo(() => {
    return tagCounts.filter((t) =>
      t.tag.toLowerCase().includes(search.toLowerCase())
    );
  }, [tagCounts, search]);

  // Stats from analytics
  const totalTags = analytics?.total_unique_tags || 0;
  const totalTagged = analytics?.total_tagged_contacts || 0;
  const avgTagsPerContact = analytics?.avg_tags_per_contact || 0;

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the crm:read permission to view tags."
        backHref="/crm"
        backLabel="Back to CRM"
      />
    );
  }

  if (analyticsLoading && !analytics) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {(analyticsError || contactsError) && (
        <ErrorDisplay
          message="Failed to load tags"
          error={(analyticsError || contactsError) as Error}
          onRetry={() => {
            mutateAnalytics();
            if (selectedTag) {
              mutateContacts();
            }
          }}
        />
      )}

      <PageHeader
        title="Tags"
        subtitle="Organize contacts with custom tags"
        icon={Tag}
        iconClassName="bg-violet-500/10 border border-violet-500/30"
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/20 rounded-lg">
              <Hash className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{totalTags}</p>
              <p className="text-xs text-slate-muted">Unique Tags</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-lg">
              <Users className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{totalTagged}</p>
              <p className="text-xs text-slate-muted">Tagged Contacts</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <Tag className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{avgTagsPerContact}</p>
              <p className="text-xs text-slate-muted">Avg Tags/Contact</p>
            </div>
          </div>
        </div>
      </div>

      {/* Selected Tag View */}
      {selectedTag && (
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Tag className="w-5 h-5 text-violet-400" />
              <h3 className="text-foreground font-semibold">Contacts tagged: "{selectedTag}"</h3>
              <span className="px-2 py-0.5 bg-violet-500/20 text-violet-400 rounded text-xs">
                {contacts.length}
              </span>
            </div>
            <Button
              onClick={() => setSelectedTag(null)}
              className="text-slate-muted text-sm hover:text-foreground transition-colors"
            >
              Clear selection
            </Button>
          </div>
          <div className="space-y-2">
            {contactsLoading && contacts.length === 0 ? (
              <div className="py-6 text-center text-slate-muted">Loading tagged contacts…</div>
            ) : (
              contacts.slice(0, 10).map((contact: UnifiedContact) => (
                <Link
                  key={contact.id}
                  href={`/crm/contacts/${contact.id}`}
                  className="flex items-center justify-between py-2 px-3 hover:bg-slate-elevated rounded-lg transition-colors"
                >
                  <div>
                    <p className="text-foreground font-medium">{contact.name}</p>
                    <p className="text-xs text-slate-muted">{contact.email}</p>
                  </div>
                  <span className="px-2 py-1 bg-slate-elevated rounded text-xs text-foreground-secondary">
                    {contact.contact_type}
                  </span>
                </Link>
              ))
            )}
            {!contactsLoading && contacts.length === 0 && (
              <div className="py-6 text-center text-slate-muted">No contacts found for this tag.</div>
            )}
            {contacts.length > 10 && (
              <Link
                href={`/crm/contacts/all?tag=${encodeURIComponent(selectedTag)}`}
                className="block text-center py-2 text-violet-400 hover:text-violet-300 text-sm"
              >
                View all {contacts.length} contacts
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Tag Cloud */}
      {!selectedTag && (
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-4 mb-4">
            <FilterInput
              type="text"
              placeholder="Search tags..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 max-w-md"
            />
          </div>

          {filteredTags.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {filteredTags.map((tagData, idx) => (
                <Button
                  key={tagData.tag}
                  onClick={() => setSelectedTag(tagData.tag)}
                  className={cn(
                    'inline-flex items-center gap-2 px-3 py-2 rounded-lg border transition-all hover:scale-105',
                    tagColors[idx % tagColors.length]
                  )}
                >
                  <Tag className="w-4 h-4" />
                  <span className="font-medium">{tagData.tag}</span>
                  <span className="px-1.5 py-0.5 bg-black/20 rounded text-xs">
                    {tagData.count}
                  </span>
                </Button>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-slate-muted">
              {search ? 'No tags match your search' : 'No tags found. Add tags to contacts to see them here.'}
            </div>
          )}
        </div>
      )}

      {/* All Tags List */}
      {!selectedTag && filteredTags.length > 0 && (
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <h3 className="text-foreground font-semibold mb-4">All Tags</h3>
          <div className="divide-y divide-slate-border">
            {filteredTags.map((tagData, idx) => (
              <div
                key={tagData.tag}
                className="flex items-center justify-between py-3 hover:bg-slate-elevated/50 px-2 rounded-lg transition-colors cursor-pointer"
                onClick={() => setSelectedTag(tagData.tag)}
              >
                <div className="flex items-center gap-3">
                  <div className={cn(
                    'w-8 h-8 rounded-lg flex items-center justify-center',
                    tagColors[idx % tagColors.length].split(' ')[0]
                  )}>
                    <Tag className="w-4 h-4" />
                  </div>
                  <span className="text-foreground">{tagData.tag}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-slate-muted">{tagData.count} contacts</span>
                  <Link
                    href={`/crm/contacts/all?tag=${encodeURIComponent(tagData.tag)}`}
                    onClick={(e) => e.stopPropagation()}
                    className="text-violet-400 hover:text-violet-300 text-sm"
                  >
                    View all
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
