'use client';

import { useState, useMemo } from 'react';
import {
  FileDown,
  Download,
  CheckCircle,
  Filter,
  Users,
  Building2,
  Mail,
  Phone,
  MapPin,
  Tag,
  Calendar,
  DollarSign,
  FileText,
  Loader2,
  CheckSquare,
  Square,
} from 'lucide-react';
import useSWR from 'swr';
import { apiFetch, useUnifiedContacts, type UnifiedContact, type UnifiedContactsParams } from '@/hooks/useApi';
import { API_BASE } from '@/lib/api/core';
import { ErrorDisplay } from '@/components/insights/shared';
import { Button, FilterCard, FilterSelect, LoadingState, PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

interface ExportField {
  key: string;
  label: string;
  group: string;
  default: boolean;
}

const EXPORT_FIELDS: ExportField[] = [
  // Basic Info
  { key: 'id', label: 'ID', group: 'Basic', default: false },
  { key: 'name', label: 'Name', group: 'Basic', default: true },
  { key: 'email', label: 'Email', group: 'Basic', default: true },
  { key: 'phone', label: 'Phone', group: 'Basic', default: true },
  { key: 'mobile', label: 'Mobile', group: 'Basic', default: false },
  { key: 'company_name', label: 'Company Name', group: 'Basic', default: true },

  // Classification
  { key: 'contact_type', label: 'Contact Type', group: 'Classification', default: true },
  { key: 'category', label: 'Category', group: 'Classification', default: true },
  { key: 'status', label: 'Status', group: 'Classification', default: true },
  { key: 'is_organization', label: 'Is Organization', group: 'Classification', default: false },
  { key: 'lead_qualification', label: 'Lead Qualification', group: 'Classification', default: false },
  { key: 'lead_score', label: 'Lead Score', group: 'Classification', default: false },

  // Address
  { key: 'address_line1', label: 'Address Line 1', group: 'Address', default: false },
  { key: 'address_line2', label: 'Address Line 2', group: 'Address', default: false },
  { key: 'city', label: 'City', group: 'Address', default: true },
  { key: 'state', label: 'State', group: 'Address', default: true },
  { key: 'postal_code', label: 'Postal Code', group: 'Address', default: false },
  { key: 'country', label: 'Country', group: 'Address', default: false },

  // Segmentation
  { key: 'territory', label: 'Territory', group: 'Segmentation', default: true },
  { key: 'industry', label: 'Industry', group: 'Segmentation', default: false },
  { key: 'market_segment', label: 'Market Segment', group: 'Segmentation', default: false },
  { key: 'tags', label: 'Tags', group: 'Segmentation', default: false },

  // Financial
  { key: 'mrr', label: 'MRR', group: 'Financial', default: false },
  { key: 'lifetime_value', label: 'Lifetime Value', group: 'Financial', default: false },
  { key: 'outstanding_balance', label: 'Outstanding Balance', group: 'Financial', default: false },
  { key: 'billing_type', label: 'Billing Type', group: 'Financial', default: false },

  // Acquisition
  { key: 'source', label: 'Source', group: 'Acquisition', default: false },
  { key: 'source_campaign', label: 'Source Campaign', group: 'Acquisition', default: false },
  { key: 'referrer', label: 'Referrer', group: 'Acquisition', default: false },

  // Dates
  { key: 'first_contact_date', label: 'First Contact Date', group: 'Dates', default: false },
  { key: 'conversion_date', label: 'Conversion Date', group: 'Dates', default: false },
  { key: 'cancellation_date', label: 'Cancellation Date', group: 'Dates', default: false },
  { key: 'created_at', label: 'Created At', group: 'Dates', default: false },
  { key: 'updated_at', label: 'Updated At', group: 'Dates', default: false },

  // Notes
  { key: 'notes', label: 'Notes', group: 'Other', default: false },
];

const FIELD_GROUPS = ['Basic', 'Classification', 'Address', 'Segmentation', 'Financial', 'Acquisition', 'Dates', 'Other'];
const CONTACT_TYPES: UnifiedContactsParams['contact_type'][] = ['lead', 'prospect', 'customer', 'churned', 'person'];
const CATEGORIES: UnifiedContactsParams['category'][] = ['residential', 'business', 'enterprise', 'government', 'non_profit'];
const STATUSES: UnifiedContactsParams['status'][] = ['active', 'inactive', 'suspended', 'do_not_contact'];

export default function CRMExportPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('crm:read');
  const [selectedFields, setSelectedFields] = useState<Set<string>>(
    new Set(EXPORT_FIELDS.filter((f) => f.default).map((f) => f.key))
  );
  const [exportFormat, setExportFormat] = useState<'csv' | 'json'>('csv');
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState(false);

  // Filters
  const [contactType, setContactType] = useState<string>('');
  const [category, setCategory] = useState<string>('');
  const [status, setStatus] = useState<string>('');

  // Fetch contacts
  const contactTypeValue = CONTACT_TYPES.includes(contactType as UnifiedContactsParams['contact_type'])
    ? (contactType as UnifiedContactsParams['contact_type'])
    : undefined;
  const categoryValue = CATEGORIES.includes(category as UnifiedContactsParams['category'])
    ? (category as UnifiedContactsParams['category'])
    : undefined;
  const statusValue = STATUSES.includes(status as UnifiedContactsParams['status'])
    ? (status as UnifiedContactsParams['status'])
    : undefined;
  const canFetch = !authLoading && !missingScope;

  const { data, isLoading, error, mutate } = useUnifiedContacts({
    page: 1,
    page_size: 1000,
    contact_type: contactTypeValue,
    category: categoryValue,
    status: statusValue,
  }, { isPaused: () => !canFetch });

  const contacts = data?.items || [];
  const totalContacts = data?.total || contacts.length;

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the crm:read permission to export contacts."
        backHref="/crm"
        backLabel="Back to CRM"
      />
    );
  }

  const toggleField = (key: string) => {
    setSelectedFields((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const toggleGroup = (group: string) => {
    const groupFields = EXPORT_FIELDS.filter((f) => f.group === group);
    const allSelected = groupFields.every((f) => selectedFields.has(f.key));

    setSelectedFields((prev) => {
      const next = new Set(prev);
      groupFields.forEach((f) => {
        if (allSelected) {
          next.delete(f.key);
        } else {
          next.add(f.key);
        }
      });
      return next;
    });
  };

  const selectAll = () => {
    setSelectedFields(new Set(EXPORT_FIELDS.map((f) => f.key)));
  };

  const selectNone = () => {
    setSelectedFields(new Set());
  };

  const handleExport = async () => {
    if (selectedFields.size === 0) {
      alert('Please select at least one field to export');
      return;
    }

    setExporting(true);

    try {
      const fields = Array.from(selectedFields);

      // Build query parameters for backend export
      const params = new URLSearchParams();
      params.set('format', exportFormat);
      params.set('fields', fields.join(','));
      if (contactType) params.set('contact_type', contactType);
      if (category) params.set('category', category);
      if (status) params.set('status', status);

      // Fetch from backend export endpoint
      const response = await fetch(`${API_BASE}/api/contacts/export?${params.toString()}`, {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error(`Export failed: ${response.statusText}`);
      }

      // Get filename from content-disposition header or generate one
      const contentDisposition = response.headers.get('content-disposition');
      let filename = `contacts_export_${new Date().toISOString().split('T')[0]}.${exportFormat}`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename=(.+)/);
        if (match) {
          filename = match[1].replace(/"/g, '');
        }
      }

      // Stream response to blob and download
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setExported(true);
      setTimeout(() => setExported(false), 3000);
    } catch (err) {
      console.error('Export error:', err);
      alert('Failed to export contacts');
    } finally {
      setExporting(false);
    }
  };

  if (isLoading && !data) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load contacts"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      {exported && (
        <div className="bg-emerald-500/20 border border-emerald-500/30 rounded-lg p-4 flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-emerald-400" />
          <span className="text-emerald-400">Export downloaded successfully!</span>
        </div>
      )}

      <PageHeader
        title="Export Contacts"
        subtitle="Download contact data in CSV or JSON format"
        icon={FileDown}
        iconClassName="bg-emerald-500/10 border border-emerald-500/30"
      />

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <Users className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{totalContacts}</p>
              <p className="text-xs text-slate-muted">Contacts to Export</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-lg">
              <CheckSquare className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{selectedFields.size}</p>
              <p className="text-xs text-slate-muted">Fields Selected</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/20 rounded-lg">
              <FileText className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{exportFormat.toUpperCase()}</p>
              <p className="text-xs text-slate-muted">Format</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <Filter className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">
                {contactType || category || status ? 'Active' : 'None'}
              </p>
              <p className="text-xs text-slate-muted">Filters</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <FilterCard
        title="Filter Contacts"
        iconClassName="text-emerald-400"
        contentClassName="grid grid-cols-1 md:grid-cols-3 gap-4"
      >
        <div>
          <label className="text-sm text-slate-muted block mb-2">Contact Type</label>
          <FilterSelect
            value={contactType}
            onChange={(e) => setContactType(e.target.value)}
            className="w-full focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="">All Types</option>
            <option value="lead">Lead</option>
            <option value="prospect">Prospect</option>
            <option value="customer">Customer</option>
            <option value="churned">Churned</option>
          </FilterSelect>
        </div>
        <div>
          <label className="text-sm text-slate-muted block mb-2">Category</label>
          <FilterSelect
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="">All Categories</option>
            <option value="residential">Residential</option>
            <option value="business">Business</option>
            <option value="enterprise">Enterprise</option>
            <option value="government">Government</option>
          </FilterSelect>
        </div>
        <div>
          <label className="text-sm text-slate-muted block mb-2">Status</label>
          <FilterSelect
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="pending">Pending</option>
          </FilterSelect>
        </div>
      </FilterCard>

      {/* Export Format */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-5">
        <div className="flex items-center gap-2 mb-4">
          <FileText className="w-4 h-4 text-emerald-400" />
          <h3 className="text-foreground font-semibold">Export Format</h3>
        </div>

        <div className="flex gap-3">
          <Button
            onClick={() => setExportFormat('csv')}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
              exportFormat === 'csv'
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : 'bg-slate-elevated text-slate-muted hover:text-foreground'
            )}
          >
            <FileText className="w-4 h-4" />
            CSV
          </Button>
          <Button
            onClick={() => setExportFormat('json')}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
              exportFormat === 'json'
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : 'bg-slate-elevated text-slate-muted hover:text-foreground'
            )}
          >
            <FileText className="w-4 h-4" />
            JSON
          </Button>
        </div>
      </div>

      {/* Field Selection */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <CheckSquare className="w-4 h-4 text-emerald-400" />
            <h3 className="text-foreground font-semibold">Select Fields</h3>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={selectAll}
              className="text-sm text-emerald-400 hover:text-emerald-300 transition-colors"
            >
              Select All
            </Button>
            <span className="text-slate-muted">|</span>
            <Button
              onClick={selectNone}
              className="text-sm text-slate-muted hover:text-foreground transition-colors"
            >
              Clear All
            </Button>
          </div>
        </div>

        <div className="space-y-6">
          {FIELD_GROUPS.map((group) => {
            const groupFields = EXPORT_FIELDS.filter((f) => f.group === group);
            const selectedCount = groupFields.filter((f) => selectedFields.has(f.key)).length;
            const allSelected = selectedCount === groupFields.length;

            return (
              <div key={group}>
                <div className="flex items-center justify-between mb-3">
                  <Button
                    onClick={() => toggleGroup(group)}
                    className="flex items-center gap-2 text-foreground font-medium hover:text-emerald-400 transition-colors"
                  >
                    {allSelected ? (
                      <CheckSquare className="w-4 h-4 text-emerald-400" />
                    ) : selectedCount > 0 ? (
                      <CheckSquare className="w-4 h-4 text-slate-muted" />
                    ) : (
                      <Square className="w-4 h-4 text-slate-muted" />
                    )}
                    {group}
                  </Button>
                  <span className="text-xs text-slate-muted">
                    {selectedCount}/{groupFields.length}
                  </span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {groupFields.map((field) => (
                    <Button
                      key={field.key}
                      onClick={() => toggleField(field.key)}
                      className={cn(
                        'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors text-left',
                        selectedFields.has(field.key)
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : 'bg-slate-elevated text-slate-muted hover:text-foreground'
                      )}
                    >
                      {selectedFields.has(field.key) ? (
                        <CheckSquare className="w-4 h-4" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                      {field.label}
                    </Button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Export Button */}
      <div className="flex flex-col items-end gap-2">
        <Button
          onClick={handleExport}
          disabled={exporting || selectedFields.size === 0}
          className={cn(
            'flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-colors',
            exporting || selectedFields.size === 0
              ? 'bg-slate-elevated text-slate-muted cursor-not-allowed'
              : 'bg-emerald-500 text-foreground hover:bg-emerald-400'
          )}
        >
          {exporting ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Exporting...
            </>
          ) : (
            <>
              <Download className="w-5 h-5" />
              Export All Matching Contacts
            </>
          )}
        </Button>
        <p className="text-xs text-slate-muted">
          Export includes all contacts matching filters (preview shows first {totalContacts})
        </p>
      </div>
    </div>
  );
}
