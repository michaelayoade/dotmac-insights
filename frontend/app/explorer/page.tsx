'use client';

import { useState, useCallback } from 'react';
import {
  Database,
  Search,
  Filter,
  Download,
  Play,
  X,
  Plus,
  ChevronDown,
  Table,
  BarChart3,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { DataTable } from '@/components/DataTable';
import { useDataExplorer } from '@/hooks/useApi';
import { formatCurrency, formatDate, cn } from '@/lib/utils';

type DataEntity = 'customers' | 'subscriptions' | 'invoices' | 'payments' | 'pops' | 'conversations';

interface FilterConfig {
  id: string;
  field: string;
  operator: 'eq' | 'gt' | 'lt' | 'gte' | 'lte' | 'like' | 'in';
  value: string;
}

const ENTITY_FIELDS: Record<DataEntity, { name: string; type: string }[]> = {
  customers: [
    { name: 'id', type: 'number' },
    { name: 'name', type: 'string' },
    { name: 'email', type: 'string' },
    { name: 'phone', type: 'string' },
    { name: 'status', type: 'string' },
    { name: 'customer_type', type: 'string' },
    { name: 'pop_id', type: 'number' },
    { name: 'signup_date', type: 'date' },
    { name: 'tenure_days', type: 'number' },
  ],
  subscriptions: [
    { name: 'id', type: 'number' },
    { name: 'customer_id', type: 'number' },
    { name: 'plan_name', type: 'string' },
    { name: 'price', type: 'number' },
    { name: 'status', type: 'string' },
    { name: 'billing_cycle', type: 'string' },
    { name: 'start_date', type: 'date' },
    { name: 'end_date', type: 'date' },
  ],
  invoices: [
    { name: 'id', type: 'number' },
    { name: 'customer_id', type: 'number' },
    { name: 'invoice_number', type: 'string' },
    { name: 'total_amount', type: 'number' },
    { name: 'status', type: 'string' },
    { name: 'invoice_date', type: 'date' },
    { name: 'due_date', type: 'date' },
  ],
  payments: [
    { name: 'id', type: 'number' },
    { name: 'customer_id', type: 'number' },
    { name: 'invoice_id', type: 'number' },
    { name: 'amount', type: 'number' },
    { name: 'payment_method', type: 'string' },
    { name: 'payment_date', type: 'date' },
    { name: 'status', type: 'string' },
  ],
  pops: [
    { name: 'id', type: 'number' },
    { name: 'name', type: 'string' },
    { name: 'code', type: 'string' },
    { name: 'city', type: 'string' },
    { name: 'state', type: 'string' },
    { name: 'status', type: 'string' },
  ],
  conversations: [
    { name: 'id', type: 'number' },
    { name: 'customer_id', type: 'number' },
    { name: 'channel', type: 'string' },
    { name: 'status', type: 'string' },
    { name: 'priority', type: 'string' },
    { name: 'created_at', type: 'date' },
  ],
};

const OPERATORS = [
  { value: 'eq', label: '=' },
  { value: 'gt', label: '>' },
  { value: 'lt', label: '<' },
  { value: 'gte', label: '>=' },
  { value: 'lte', label: '<=' },
  { value: 'like', label: 'contains' },
  { value: 'in', label: 'in list' },
];

export default function ExplorerPage() {
  const [entity, setEntity] = useState<DataEntity>('customers');
  const [filters, setFilters] = useState<FilterConfig[]>([]);
  const [selectedFields, setSelectedFields] = useState<string[]>([]);
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [shouldFetch, setShouldFetch] = useState(false);
  const [viewMode, setViewMode] = useState<'table' | 'json'>('table');

  // Build query params
  const buildQueryParams = useCallback(() => {
    const params: Record<string, unknown> = {
      limit,
      offset,
    };

    if (selectedFields.length > 0) {
      params.fields = selectedFields;
    }

    filters.forEach((f) => {
      if (f.field && f.value) {
        if (f.operator === 'eq') {
          params[f.field] = f.value;
        } else {
          params[f.field] = { [f.operator]: f.value };
        }
      }
    });

    return params;
  }, [filters, selectedFields, limit, offset]);

  const { data, isLoading, error } = useDataExplorer(
    shouldFetch ? entity : null,
    shouldFetch ? buildQueryParams() : {}
  );

  const addFilter = () => {
    setFilters([
      ...filters,
      { id: crypto.randomUUID(), field: '', operator: 'eq', value: '' },
    ]);
  };

  const updateFilter = (id: string, updates: Partial<FilterConfig>) => {
    setFilters(filters.map((f) => (f.id === id ? { ...f, ...updates } : f)));
  };

  const removeFilter = (id: string) => {
    setFilters(filters.filter((f) => f.id !== id));
  };

  const toggleField = (field: string) => {
    if (selectedFields.includes(field)) {
      setSelectedFields(selectedFields.filter((f) => f !== field));
    } else {
      setSelectedFields([...selectedFields, field]);
    }
  };

  const runQuery = () => {
    setOffset(0);
    setShouldFetch(true);
  };

  const resetQuery = () => {
    setFilters([]);
    setSelectedFields([]);
    setLimit(50);
    setOffset(0);
    setShouldFetch(false);
  };

  const exportData = () => {
    if (!data?.data) return;

    const csv = [
      Object.keys(data.data[0] || {}).join(','),
      ...data.data.map((row) =>
        Object.values(row)
          .map((v) => (typeof v === 'string' ? `"${v}"` : v))
          .join(',')
      ),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${entity}_export_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const fields = ENTITY_FIELDS[entity];

  // Generate columns dynamically based on data
  const columns = data?.data?.[0]
    ? Object.keys(data.data[0]).map((key) => ({
        key,
        header: key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        sortable: true,
        render: (item: Record<string, unknown>) => {
          const value = item[key];
          if (value === null || value === undefined) return '—';
          if (typeof value === 'boolean') return value ? 'Yes' : 'No';
          if (key.includes('amount') || key.includes('price') || key === 'mrr' || key === 'outstanding') {
            return (
              <span className="text-teal-electric font-mono">
                {formatCurrency(value as number)}
              </span>
            );
          }
          if (key.includes('date') || key.includes('_at')) {
            return formatDate(value as string);
          }
          if (key === 'status') {
            return (
              <Badge
                variant={
                  value === 'active' ? 'success' :
                  value === 'paid' ? 'success' :
                  value === 'cancelled' || value === 'failed' ? 'danger' :
                  value === 'pending' || value === 'overdue' ? 'warning' :
                  'muted'
                }
                size="sm"
              >
                {String(value)}
              </Badge>
            );
          }
          return String(value);
        },
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-white">Data Explorer</h1>
          <p className="text-slate-muted mt-1">
            Query and analyze your business data
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="info">
            <Database className="w-3 h-3 mr-1" />
            {entity}
          </Badge>
          {data && (
            <Badge variant="muted">
              {data.total.toLocaleString()} records
            </Badge>
          )}
        </div>
      </div>

      {/* Query Builder */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Query Builder</CardTitle>
              <CardDescription>Select entity, fields, and filters</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={resetQuery}
                className="px-3 py-1.5 text-sm text-slate-muted hover:text-white transition-colors"
              >
                Reset
              </button>
              <button
                onClick={runQuery}
                className="flex items-center gap-2 px-4 py-2 bg-teal-electric text-slate-deep font-semibold rounded-lg hover:bg-teal-glow transition-colors"
              >
                <Play className="w-4 h-4" />
                Run Query
              </button>
            </div>
          </div>
        </CardHeader>

        <div className="space-y-6">
          {/* Entity Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-muted mb-2">
              Entity
            </label>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(ENTITY_FIELDS) as DataEntity[]).map((e) => (
                <button
                  key={e}
                  onClick={() => {
                    setEntity(e);
                    setSelectedFields([]);
                    setFilters([]);
                    setShouldFetch(false);
                  }}
                  className={cn(
                    'px-4 py-2 rounded-lg text-sm font-medium transition-all capitalize',
                    entity === e
                      ? 'bg-teal-electric/20 text-teal-electric border border-teal-electric/30'
                      : 'bg-slate-elevated text-slate-muted hover:text-white border border-slate-border'
                  )}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>

          {/* Field Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-muted mb-2">
              Fields <span className="text-xs">(leave empty for all)</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {fields.map((field) => (
                <button
                  key={field.name}
                  onClick={() => toggleField(field.name)}
                  className={cn(
                    'px-3 py-1.5 rounded-md text-sm transition-all',
                    selectedFields.includes(field.name)
                      ? 'bg-teal-electric/20 text-teal-electric'
                      : 'bg-slate-elevated text-slate-muted hover:text-white'
                  )}
                >
                  {field.name}
                  <span className="ml-1 text-xs opacity-60">({field.type})</span>
                </button>
              ))}
            </div>
          </div>

          {/* Filters */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-slate-muted">
                Filters
              </label>
              <button
                onClick={addFilter}
                className="flex items-center gap-1 text-sm text-teal-electric hover:text-teal-glow transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Filter
              </button>
            </div>

            {filters.length === 0 ? (
              <p className="text-slate-muted text-sm py-4 text-center border border-dashed border-slate-border rounded-lg">
                No filters applied. Click "Add Filter" to narrow your results.
              </p>
            ) : (
              <div className="space-y-2">
                {filters.map((filter) => (
                  <div
                    key={filter.id}
                    className="flex items-center gap-2 p-3 bg-slate-elevated rounded-lg"
                  >
                    <select
                      value={filter.field}
                      onChange={(e) => updateFilter(filter.id, { field: e.target.value })}
                      className="flex-1 px-3 py-2 bg-slate-card border border-slate-border rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                    >
                      <option value="">Select field...</option>
                      {fields.map((f) => (
                        <option key={f.name} value={f.name}>
                          {f.name}
                        </option>
                      ))}
                    </select>

                    <select
                      value={filter.operator}
                      onChange={(e) =>
                        updateFilter(filter.id, {
                          operator: e.target.value as FilterConfig['operator'],
                        })
                      }
                      className="w-28 px-3 py-2 bg-slate-card border border-slate-border rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                    >
                      {OPERATORS.map((op) => (
                        <option key={op.value} value={op.value}>
                          {op.label}
                        </option>
                      ))}
                    </select>

                    <input
                      type="text"
                      value={filter.value}
                      onChange={(e) => updateFilter(filter.id, { value: e.target.value })}
                      placeholder="Value..."
                      className="flex-1 px-3 py-2 bg-slate-card border border-slate-border rounded-lg text-white text-sm placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                    />

                    <button
                      onClick={() => removeFilter(filter.id)}
                      className="p-2 text-slate-muted hover:text-coral-alert transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Limit */}
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-slate-muted">Limit:</label>
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              {[10, 25, 50, 100, 250, 500].map((n) => (
                <option key={n} value={n}>
                  {n} rows
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {/* Results */}
      {shouldFetch && (
        <Card padding="none">
          <div className="p-6 border-b border-slate-border flex items-center justify-between">
            <div>
              <CardTitle>Results</CardTitle>
              {data && (
                <CardDescription>
                  Showing {data.data.length} of {data.total.toLocaleString()} records
                </CardDescription>
              )}
            </div>
            <div className="flex items-center gap-2">
              {/* View Toggle */}
              <div className="flex items-center bg-slate-elevated rounded-lg p-1">
                <button
                  onClick={() => setViewMode('table')}
                  className={cn(
                    'p-2 rounded-md transition-colors',
                    viewMode === 'table'
                      ? 'bg-teal-electric/20 text-teal-electric'
                      : 'text-slate-muted hover:text-white'
                  )}
                >
                  <Table className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setViewMode('json')}
                  className={cn(
                    'p-2 rounded-md transition-colors',
                    viewMode === 'json'
                      ? 'bg-teal-electric/20 text-teal-electric'
                      : 'text-slate-muted hover:text-white'
                  )}
                >
                  <BarChart3 className="w-4 h-4" />
                </button>
              </div>

              {/* Export Button */}
              {data && data.data.length > 0 && (
                <button
                  onClick={exportData}
                  className="flex items-center gap-2 px-3 py-2 text-sm text-slate-muted hover:text-white border border-slate-border rounded-lg transition-colors"
                >
                  <Download className="w-4 h-4" />
                  Export CSV
                </button>
              )}
            </div>
          </div>

          {error ? (
            <div className="p-8 text-center">
              <p className="text-coral-alert">Error loading data: {error.message}</p>
            </div>
          ) : viewMode === 'table' ? (
            <>
              <DataTable
                columns={columns}
                data={(data?.data || []) as Record<string, unknown>[]}
                keyField="id"
                loading={isLoading}
                emptyMessage="No results found"
              />
              {data && data.total > limit && (
                <div className="flex items-center justify-between px-6 py-4 border-t border-slate-border">
                  <span className="text-slate-muted text-sm">
                    Page {Math.floor(offset / limit) + 1} of {Math.ceil(data.total / limit)}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setOffset(Math.max(0, offset - limit))}
                      disabled={offset === 0}
                      className="px-3 py-1.5 text-sm rounded-lg border border-slate-border text-slate-muted hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Previous
                    </button>
                    <button
                      onClick={() => setOffset(offset + limit)}
                      disabled={offset + limit >= data.total}
                      className="px-3 py-1.5 text-sm rounded-lg border border-slate-border text-slate-muted hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="p-6 max-h-[600px] overflow-auto">
              <pre className="text-sm text-slate-muted font-mono whitespace-pre-wrap">
                {JSON.stringify(data?.data || [], null, 2)}
              </pre>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
