'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Copy,
  Search,
  Users,
  Mail,
  Phone,
  User,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Merge,
  Trash2,
  Eye,
} from 'lucide-react';
import useSWR from 'swr';
import { apiFetch, useUnifiedContacts, type UnifiedContact } from '@/hooks/useApi';
import { fetchApi } from '@/lib/api/core';
import { ErrorDisplay } from '@/components/insights/shared';
import { Button, LoadingState, PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';
import { formatDate } from '@/lib/formatters';
import { useAuth, useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

interface DuplicateGroup {
  value: string;
  count: number;
  contact_ids: number[];
}

interface DuplicatesResponse {
  field: string;
  duplicate_groups: DuplicateGroup[];
  total_groups: number;
}

export default function CRMDuplicatesPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('crm:read');
  const router = useRouter();
  const { hasScope } = useAuth();
  const canWrite = hasScope('crm:write');
  const [field, setField] = useState<'email' | 'phone' | 'name'>('email');
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);
  const [selectedPrimary, setSelectedPrimary] = useState<Record<string, number>>({});
  const [merging, setMerging] = useState(false);
  const [mergeSuccess, setMergeSuccess] = useState<string | null>(null);
  const canFetch = !authLoading && !missingScope;

  const { data, isLoading, error, mutate } = useSWR<DuplicatesResponse>(
    canFetch ? `/contacts/duplicates?field=${field}&limit=50` : null,
    apiFetch
  );

  const duplicateGroups = data?.duplicate_groups || [];
  const totalGroups = data?.total_groups || 0;
  const totalDuplicates = duplicateGroups.reduce((sum, g) => sum + g.count, 0);

  // Stats
  const canMerge = Object.keys(selectedPrimary).length > 0;

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the crm:read permission to view duplicates."
        backHref="/crm"
        backLabel="Back to CRM"
      />
    );
  }

  const handleMerge = async (group: DuplicateGroup) => {
    const primaryId = selectedPrimary[group.value];
    if (!primaryId) {
      alert('Please select a primary contact to keep');
      return;
    }

    const duplicateIds = group.contact_ids.filter((id) => id !== primaryId);
    if (duplicateIds.length === 0) {
      alert('No duplicates to merge');
      return;
    }

    setMerging(true);
    try {
      await fetchApi('/contacts/merge', {
        method: 'POST',
        body: JSON.stringify({
          primary_contact_id: primaryId,
          duplicate_contact_ids: duplicateIds,
          merge_strategy: 'merge_all',
        }),
      });

      setMergeSuccess(`Merged ${duplicateIds.length} contacts into #${primaryId}`);
      setSelectedPrimary((prev) => {
        const next = { ...prev };
        delete next[group.value];
        return next;
      });
      mutate();

      setTimeout(() => setMergeSuccess(null), 3000);
    } catch (err) {
      alert('Failed to merge contacts. Please try again.');
    } finally {
      setMerging(false);
    }
  };

  if (isLoading && !data) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load duplicates"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      {mergeSuccess && (
        <div className="bg-emerald-500/20 border border-emerald-500/30 rounded-lg p-4 flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-emerald-400" />
          <span className="text-emerald-400">{mergeSuccess}</span>
        </div>
      )}

      <PageHeader
        title="Duplicate Detection"
        subtitle="Find and merge duplicate contact records"
        icon={Copy}
        iconClassName="bg-orange-500/10 border border-orange-500/30"
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-500/20 rounded-lg">
              <Copy className="w-5 h-5 text-orange-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{totalGroups}</p>
              <p className="text-xs text-slate-muted">Duplicate Groups</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/20 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-red-400">{totalDuplicates}</p>
              <p className="text-xs text-slate-muted">Total Duplicates</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-lg">
              <Users className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">
                {totalDuplicates - totalGroups}
              </p>
              <p className="text-xs text-slate-muted">To Remove</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <Merge className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">
                {Object.keys(selectedPrimary).length}
              </p>
              <p className="text-xs text-slate-muted">Ready to Merge</p>
            </div>
          </div>
        </div>
      </div>

      {/* Field Selection */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-4">
        <div className="flex items-center gap-4">
          <span className="text-foreground text-sm font-medium">Find duplicates by:</span>
          <div className="flex gap-2">
            <Button
              onClick={() => setField('email')}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                field === 'email'
                  ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                  : 'text-slate-muted hover:text-foreground hover:bg-slate-elevated'
              )}
            >
              <Mail className="w-4 h-4" />
              Email
            </Button>
            <Button
              onClick={() => setField('phone')}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                field === 'phone'
                  ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                  : 'text-slate-muted hover:text-foreground hover:bg-slate-elevated'
              )}
            >
              <Phone className="w-4 h-4" />
              Phone
            </Button>
            <Button
              onClick={() => setField('name')}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                field === 'name'
                  ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                  : 'text-slate-muted hover:text-foreground hover:bg-slate-elevated'
              )}
            >
              <User className="w-4 h-4" />
              Name
            </Button>
          </div>
        </div>
      </div>

      {/* Duplicate Groups */}
      <div className="space-y-3">
        {duplicateGroups.map((group) => (
          <DuplicateGroupCard
            key={group.value}
            group={group}
            field={field}
            isExpanded={expandedGroup === group.value}
            onToggle={() => setExpandedGroup(expandedGroup === group.value ? null : group.value)}
            selectedPrimary={selectedPrimary[group.value]}
            onSelectPrimary={(id) =>
              setSelectedPrimary((prev) => ({ ...prev, [group.value]: id }))
            }
            onMerge={() => handleMerge(group)}
            merging={merging}
            canWrite={canWrite}
          />
        ))}
      </div>

      {duplicateGroups.length === 0 && !isLoading && (
        <div className="bg-slate-card rounded-xl border border-slate-border p-8 text-center">
          <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
          <h3 className="text-foreground font-semibold mb-2">No Duplicates Found</h3>
          <p className="text-slate-muted text-sm">
            No duplicate contacts were found based on {field}. Your data looks clean!
          </p>
        </div>
      )}
    </div>
  );
}

function DuplicateGroupCard({
  group,
  field,
  isExpanded,
  onToggle,
  selectedPrimary,
  onSelectPrimary,
  onMerge,
  merging,
  canWrite,
}: {
  group: DuplicateGroup;
  field: string;
  isExpanded: boolean;
  onToggle: () => void;
  selectedPrimary?: number;
  onSelectPrimary: (id: number) => void;
  onMerge: () => void;
  merging: boolean;
  canWrite: boolean;
}) {
  // Fetch contact details when expanded
  const { data } = useSWR<{ items: UnifiedContact[] }>(
    isExpanded ? `/contacts?ids=${group.contact_ids.join(',')}` : null,
    apiFetch
  );

  // Try fetching individual contacts if the ids param doesn't work
  const contacts = data?.items || [];

  return (
    <div className="bg-slate-card rounded-xl border border-slate-border overflow-hidden">
      <Button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-elevated/50 transition-colors"
      >
        <div className="flex items-center gap-4">
          <div className="p-2 bg-orange-500/20 rounded-lg">
            {field === 'email' ? (
              <Mail className="w-5 h-5 text-orange-400" />
            ) : field === 'phone' ? (
              <Phone className="w-5 h-5 text-orange-400" />
            ) : (
              <User className="w-5 h-5 text-orange-400" />
            )}
          </div>
          <div className="text-left">
            <p className="text-foreground font-medium">{group.value || '(Empty)'}</p>
            <p className="text-sm text-slate-muted">{group.count} duplicate contacts</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs">
            {group.count - 1} to remove
          </span>
          {isExpanded ? (
            <ChevronDown className="w-5 h-5 text-slate-muted" />
          ) : (
            <ChevronRight className="w-5 h-5 text-slate-muted" />
          )}
        </div>
      </Button>

      {isExpanded && (
        <div className="border-t border-slate-border p-4 space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-muted">
              {canWrite
                ? 'Select the primary contact to keep. Other records will be merged into it.'
                : 'You need crm:write permission to merge duplicates.'}
            </p>
            <Button
              onClick={onMerge}
              disabled={!canWrite || !selectedPrimary || merging}
              title={!canWrite ? 'You need crm:write permission to merge duplicates' : undefined}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                canWrite && selectedPrimary
                  ? 'bg-emerald-500 text-foreground hover:bg-emerald-400'
                  : 'bg-slate-elevated text-slate-muted cursor-not-allowed'
              )}
            >
              <Merge className="w-4 h-4" />
              {merging ? 'Merging...' : 'Merge Selected'}
            </Button>
          </div>

          <div className="space-y-2">
            {group.contact_ids.map((contactId) => {
              const contact = contacts.find((c) => c.id === contactId);
              const isSelected = selectedPrimary === contactId;

              return (
                <div
                  key={contactId}
                  onClick={() => onSelectPrimary(contactId)}
                  className={cn(
                    'flex items-center justify-between p-3 rounded-lg border transition-colors cursor-pointer',
                    isSelected
                      ? 'bg-emerald-500/10 border-emerald-500/30'
                      : 'bg-slate-elevated border-slate-border hover:border-slate-muted'
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        'w-5 h-5 rounded-full border-2 flex items-center justify-center',
                        isSelected
                          ? 'border-emerald-500 bg-emerald-500'
                          : 'border-slate-muted'
                      )}
                    >
                      {isSelected && <CheckCircle className="w-3 h-3 text-foreground" />}
                    </div>
                    <div>
                      <p className="text-foreground font-medium">
                        {contact?.name || `Contact #${contactId}`}
                      </p>
                      <div className="flex items-center gap-3 text-xs text-slate-muted">
                        {contact?.email && <span>{contact.email}</span>}
                        {contact?.phone && <span>{contact.phone}</span>}
                        {contact?.contact_type && (
                          <span className="px-1.5 py-0.5 bg-slate-card rounded">
                            {contact.contact_type}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={(e) => {
                        e.stopPropagation();
                        window.open(`/crm/contacts/${contactId}`, '_blank');
                      }}
                      className="p-2 text-slate-muted hover:text-foreground transition-colors"
                      title="View contact"
                    >
                      <Eye className="w-4 h-4" />
                    </Button>
                    {isSelected && (
                      <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs">
                        Primary
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="text-xs text-slate-muted bg-slate-elevated rounded-lg p-3">
            <strong>Merge will:</strong> Combine contact details, merge tags, sum statistics,
            reassign child contacts, and delete duplicate records.
          </div>
        </div>
      )}
    </div>
  );
}
