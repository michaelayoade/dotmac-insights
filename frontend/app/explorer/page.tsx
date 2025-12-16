'use client';

import { useState, useMemo, useCallback } from 'react';
import {
  Database,
  Search,
  Download,
  ChevronDown,
  ChevronRight,
  Table,
  BarChart3,
  Calendar,
  RefreshCw,
  FileJson,
  X,
  Layers,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { DataTable } from '@/components/DataTable';
import { DateRangePicker, DateRange } from '@/components/DateRangePicker';
import { useTablesEnhanced, useTableDataEnhanced } from '@/hooks/useApi';
import { api, EnhancedTableInfo } from '@/lib/api';
import { formatCurrency, formatDate, cn } from '@/lib/utils';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';

export default function ExplorerPage() {
  const { hasAccess, isLoading: authLoading } = useRequireScope('explore:read');
  const swrGuard = { isPaused: () => authLoading || !hasAccess };

  // All hooks must be called before any conditional returns
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['core_business']));
  const [searchQuery, setSearchQuery] = useState('');
  const [tableSearchQuery, setTableSearchQuery] = useState('');
  const [dateRange, setDateRange] = useState<DateRange>({ startDate: null, endDate: null });
  const [selectedDateColumn, setSelectedDateColumn] = useState<string>('');
  const [limit, setLimit] = useState(100);
  const [offset, setOffset] = useState(0);
  const [orderBy, setOrderBy] = useState<string>('');
  const [orderDir, setOrderDir] = useState<'asc' | 'desc'>('desc');
  const [viewMode, setViewMode] = useState<'table' | 'json'>('table');
  const [exporting, setExporting] = useState(false);

  const { data: tablesData, isLoading: tablesLoading, error: tablesError, mutate: retryTables } = useTablesEnhanced(swrGuard);

  const queryParams = useMemo(() => {
    const params: Record<string, unknown> = {
      limit,
      offset,
    };
    if (orderBy) {
      params.order_by = orderBy;
      params.order_dir = orderDir;
    }
    if (selectedDateColumn && dateRange.startDate && dateRange.endDate) {
      params.date_column = selectedDateColumn;
      params.start_date = dateRange.startDate.toISOString().split('T')[0];
      params.end_date = dateRange.endDate.toISOString().split('T')[0];
    }
    if (tableSearchQuery) {
      params.search = tableSearchQuery;
    }
    return params;
  }, [limit, offset, orderBy, orderDir, selectedDateColumn, dateRange, tableSearchQuery]);

  const { data: tableData, isLoading: tableLoading, error: tableError, mutate: refetchTableData } = useTableDataEnhanced(
    selectedTable,
    queryParams as {
      limit?: number;
      offset?: number;
      order_by?: string;
      order_dir?: 'asc' | 'desc';
      date_column?: string;
      start_date?: string;
      end_date?: string;
      search?: string;
    },
    swrGuard
  );

  const selectedTableInfo = useMemo(() => {
    if (!selectedTable || !tablesData?.tables) return null;
    return tablesData.tables[selectedTable];
  }, [selectedTable, tablesData]);

  const filteredCategories = useMemo(() => {
    if (!tablesData?.by_category) return {};
    if (!searchQuery) return tablesData.by_category;

    const filtered: Record<string, EnhancedTableInfo[]> = {};
    Object.entries(tablesData.by_category).forEach(([category, tables]) => {
      const matchingTables = tables.filter(
        (t) =>
          t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          t.category_label.toLowerCase().includes(searchQuery.toLowerCase())
      );
      if (matchingTables.length > 0) {
        filtered[category] = matchingTables;
      }
    });
    return filtered;
  }, [tablesData?.by_category, searchQuery]);

  const columns = useMemo(() => {
    if (!tableData?.data?.[0]) return [];
    return Object.keys(tableData.data[0]).map((key) => ({
      key,
      header: key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      sortable: true,
      render: (item: Record<string, unknown>) => {
        const value = item[key];
        if (value === null || value === undefined) return <span className="text-slate-muted">-</span>;
        if (typeof value === 'boolean') return value ? 'Yes' : 'No';
        if (
          key.includes('amount') ||
          key.includes('price') ||
          key === 'mrr' ||
          key === 'outstanding' ||
          key === 'total' ||
          key.includes('_total')
        ) {
          return (
            <span className="text-teal-electric font-mono">
              {formatCurrency(value as number)}
            </span>
          );
        }
        if (key.includes('date') || key.includes('_at') || key.includes('created') || key.includes('updated')) {
          return formatDate(value as string);
        }
        if (key === 'status') {
          return (
            <Badge
              variant={
                value === 'active' || value === 'paid' || value === 'completed'
                  ? 'success'
                  : value === 'cancelled' || value === 'failed' || value === 'blocked'
                    ? 'danger'
                    : value === 'pending' || value === 'overdue' || value === 'new'
                      ? 'warning'
                      : 'default'
              }
              size="sm"
            >
              {String(value)}
            </Badge>
          );
        }
        const strValue = String(value);
        if (strValue.length > 100) {
          return <span title={strValue}>{strValue.slice(0, 100)}...</span>;
        }
        return strValue;
      },
    }));
  }, [tableData?.data]);

  // Auth loading state - after all hooks
  if (authLoading) {
    return <LoadingState />;
  }

  // Access denied state
  if (!hasAccess) {
    return <AccessDenied />;
  }

  const toggleCategory = (category: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(category)) {
      newExpanded.delete(category);
    } else {
      newExpanded.add(category);
    }
    setExpandedCategories(newExpanded);
  };

  const selectTable = (tableName: string) => {
    setSelectedTable(tableName);
    setOffset(0);
    setOrderBy('');
    setTableSearchQuery('');
    setSelectedDateColumn('');
    setDateRange({ startDate: null, endDate: null });
  };

  const handleSort = (column: string) => {
    if (orderBy === column) {
      setOrderDir(orderDir === 'asc' ? 'desc' : 'asc');
    } else {
      setOrderBy(column);
      setOrderDir('desc');
    }
    setOffset(0);
  };

  const handleExport = async (format: 'csv' | 'json') => {
    if (!selectedTable) return;
    setExporting(true);
    try {
      const blob = await api.exportTableData(selectedTable, format, {
        date_column: selectedDateColumn || undefined,
        start_date: dateRange.startDate?.toISOString().split('T')[0],
        end_date: dateRange.endDate?.toISOString().split('T')[0],
        search: tableSearchQuery || undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedTable}_export_${new Date().toISOString().split('T')[0]}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-6">
      {/* Sidebar - Table List */}
      <div className="w-80 flex-shrink-0 flex flex-col bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="p-4 border-b border-slate-border">
          <h2 className="font-display text-lg font-semibold text-white flex items-center gap-2">
            <Database className="w-5 h-5 text-teal-electric" />
            Data Models
          </h2>
          <p className="text-sm text-slate-muted mt-1">
            {tablesData?.total_tables || 0} tables, {tablesData?.total_records?.toLocaleString() || 0} records
          </p>
          <div className="mt-3 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              type="text"
              placeholder="Search tables..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {tablesLoading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="w-5 h-5 text-slate-muted animate-spin" />
            </div>
          ) : tablesError ? (
            <div className="p-3">
              <ErrorDisplay
                message="Failed to load tables."
                error={tablesError as Error}
                onRetry={() => retryTables()}
              />
            </div>
          ) : (
            Object.entries(filteredCategories).map(([category, tables]) => (
              <div key={category} className="mb-2">
                <button
                  onClick={() => toggleCategory(category)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-muted hover:text-white transition-colors"
                >
                  {expandedCategories.has(category) ? (
                    <ChevronDown className="w-4 h-4" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                  <Layers className="w-4 h-4" />
                  <span className="flex-1 text-left">
                    {tablesData?.categories[category] || category}
                  </span>
                  <Badge variant="default" size="sm">
                    {tables.length}
                  </Badge>
                </button>
                {expandedCategories.has(category) && (
                  <div className="ml-4 space-y-0.5">
                    {tables.map((table) => (
                      <button
                        key={table.name}
                        onClick={() => selectTable(table.name)}
                        className={cn(
                          'w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all',
                          selectedTable === table.name
                            ? 'bg-teal-electric/20 text-teal-electric'
                            : 'text-slate-muted hover:text-white hover:bg-slate-elevated'
                        )}
                      >
                        <span className="truncate">{table.name}</span>
                        <span className="text-xs opacity-60">{table.count.toLocaleString()}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {!selectedTable ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Database className="w-12 h-12 text-slate-muted mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-white mb-2">Select a Table</h3>
              <p className="text-slate-muted">Choose a data model from the sidebar to explore</p>
            </div>
          </div>
        ) : (
          <>
            {/* Table Header */}
            <Card className="flex-shrink-0">
              <CardHeader>
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Table className="w-5 h-5 text-teal-electric" />
                      {selectedTable}
                    </CardTitle>
                    <CardDescription>
                      {selectedTableInfo?.category_label} - {selectedTableInfo?.count.toLocaleString()} records
                      {selectedTableInfo?.date_columns.length ? (
                        <span className="ml-2">
                          <Calendar className="w-3 h-3 inline mr-1" />
                          {selectedTableInfo.date_columns.length} date columns
                        </span>
                      ) : null}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => refetchTableData()}
                      className="p-2 text-slate-muted hover:text-white transition-colors"
                      title="Refresh"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
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
                        <FileJson className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </CardHeader>

              {/* Filters */}
              <div className="flex flex-wrap items-center gap-3">
                {/* Search */}
                <div className="relative flex-1 min-w-[200px] max-w-md">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
                  <input
                    type="text"
                    placeholder="Search in table..."
                    value={tableSearchQuery}
                    onChange={(e) => {
                      setTableSearchQuery(e.target.value);
                      setOffset(0);
                    }}
                    className="w-full pl-9 pr-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  />
                </div>

                {/* Date Column Selector */}
                {selectedTableInfo?.date_columns && selectedTableInfo.date_columns.length > 0 && (
                  <select
                    value={selectedDateColumn}
                    onChange={(e) => setSelectedDateColumn(e.target.value)}
                    className="px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  >
                    <option value="">No date filter</option>
                    {selectedTableInfo.date_columns.map((col) => (
                      <option key={col} value={col}>
                        {col}
                      </option>
                    ))}
                  </select>
                )}

                {/* Date Range Picker */}
                {selectedDateColumn && (
                  <DateRangePicker value={dateRange} onChange={setDateRange} />
                )}

                {/* Limit */}
                <select
                  value={limit}
                  onChange={(e) => {
                    setLimit(Number(e.target.value));
                    setOffset(0);
                  }}
                  className="px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                >
                  {[25, 50, 100, 250, 500].map((n) => (
                    <option key={n} value={n}>
                      {n} rows
                    </option>
                  ))}
                </select>

                {/* Export Buttons */}
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleExport('csv')}
                    disabled={exporting || !tableData?.data?.length}
                    className="flex items-center gap-1 px-3 py-2 text-sm text-slate-muted hover:text-white border border-slate-border rounded-lg transition-colors disabled:opacity-50"
                  >
                    <Download className="w-4 h-4" />
                    CSV
                  </button>
                  <button
                    onClick={() => handleExport('json')}
                    disabled={exporting || !tableData?.data?.length}
                    className="flex items-center gap-1 px-3 py-2 text-sm text-slate-muted hover:text-white border border-slate-border rounded-lg transition-colors disabled:opacity-50"
                  >
                    <FileJson className="w-4 h-4" />
                    JSON
                  </button>
                </div>

                {/* Active Filters */}
                {(tableSearchQuery || selectedDateColumn) && (
                  <button
                    onClick={() => {
                      setTableSearchQuery('');
                      setSelectedDateColumn('');
                      setDateRange({ startDate: null, endDate: null });
                    }}
                    className="flex items-center gap-1 px-2 py-1 text-xs text-coral-alert hover:text-coral-alert/80 transition-colors"
                  >
                    <X className="w-3 h-3" />
                    Clear filters
                  </button>
                )}
              </div>
            </Card>

            {/* Data Display */}
            <Card padding="none" className="flex-1 flex flex-col min-h-0 mt-4">
              {tableError ? (
                <div className="p-6">
                  <ErrorDisplay
                    message="Failed to load table data."
                    error={tableError as Error}
                    onRetry={() => refetchTableData()}
                  />
                </div>
              ) : viewMode === 'table' ? (
                <div className="flex-1 flex flex-col min-h-0">
                  <div className="flex-1 overflow-auto">
                    <DataTable
                      columns={columns}
                      data={(tableData?.data || []) as Record<string, unknown>[]}
                      keyField="id"
                      loading={tableLoading}
                      emptyMessage="No records found"
                    />
                  </div>

                  {/* Pagination */}
                  {tableData && tableData.total > limit && (
                    <div className="flex items-center justify-between px-6 py-4 border-t border-slate-border bg-slate-card flex-shrink-0">
                      <span className="text-slate-muted text-sm">
                        Showing {offset + 1} - {Math.min(offset + limit, tableData.total)} of{' '}
                        {tableData.total.toLocaleString()} records
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setOffset(Math.max(0, offset - limit))}
                          disabled={offset === 0}
                          className="px-3 py-1.5 text-sm rounded-lg border border-slate-border text-slate-muted hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Previous
                        </button>
                        <span className="text-sm text-slate-muted">
                          Page {Math.floor(offset / limit) + 1} of {Math.ceil(tableData.total / limit)}
                        </span>
                        <button
                          onClick={() => setOffset(offset + limit)}
                          disabled={offset + limit >= tableData.total}
                          className="px-3 py-1.5 text-sm rounded-lg border border-slate-border text-slate-muted hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex-1 p-6 overflow-auto">
                  <pre className="text-sm text-slate-muted font-mono whitespace-pre-wrap">
                    {JSON.stringify(tableData?.data || [], null, 2)}
                  </pre>
                </div>
              )}
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
