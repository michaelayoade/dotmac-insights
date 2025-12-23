'use client';

import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';
import type { ModuleKey } from '@/lib/config/modules';
import type { UseListPageReturn } from '@/hooks/useListPage';
import type { TableColumn, EmptyStateConfig } from '@/lib/types/components';
import type { Variant } from '@/lib/design-tokens';

import {
  PageHeader,
  EmptyState,
  ErrorState,
  LoadingState,
  FilterCard,
  FilterInput,
  FilterSelect,
  SearchInput,
  Button,
  LinkButton,
  StatGrid,
} from '@/components/ui';
import { DataTable, Pagination } from '@/components/DataTable';
import { StatCard } from '@/components/StatCard';
import { Filter, X } from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

export interface SummaryCard {
  /** Card label */
  label: string;
  /** Card value */
  value: React.ReactNode;
  /** Optional icon */
  icon?: LucideIcon;
  /** Variant for coloring */
  variant?: Variant;
  /** Optional subtitle/trend */
  subtitle?: string;
  /** Color class override */
  colorClass?: string;
}

export interface FilterInputConfig {
  /** Filter field name (must match key in filters state) */
  name: string;
  /** Input type */
  type: 'text' | 'select' | 'date';
  /** Label for the input */
  label?: string;
  /** Placeholder text */
  placeholder?: string;
  /** Options for select type */
  options?: Array<{ value: string; label: string }>;
  /** Custom class name */
  className?: string;
}

export interface ListPageTemplateProps<T, TSortField extends string = string> {
  // ===== Module Context =====
  /** Module key for theming (e.g., 'books', 'sales') */
  module: ModuleKey;

  // ===== Page Header =====
  /** Page title */
  title: string;
  /** Page subtitle/description */
  subtitle?: string;
  /** Page icon */
  icon?: LucideIcon;
  /** Breadcrumb navigation */
  breadcrumbs?: Array<{ label: string; href?: string }>;

  // ===== Primary Action =====
  /** Primary action button (e.g., "New Invoice") */
  primaryAction?: {
    label: string;
    href?: string;
    onClick?: () => void;
    icon?: LucideIcon;
  };

  // ===== Secondary Actions =====
  /** Additional action buttons */
  secondaryActions?: React.ReactNode;

  // ===== Summary Cards =====
  /** Summary stat cards displayed above filters */
  summaryCards?: SummaryCard[];
  /** Number of columns for summary cards grid */
  summaryColumns?: 2 | 3 | 4;

  // ===== Filters =====
  /** Filter input configurations */
  filterInputs?: FilterInputConfig[];
  /** Show search input (uses filters.search) */
  showSearch?: boolean;
  /** Search placeholder */
  searchPlaceholder?: string;
  /** Show clear filters button when filters are active */
  showClearFilters?: boolean;
  /** Custom filter content (replaces filterInputs) */
  customFilters?: React.ReactNode;

  // ===== Table =====
  /** Table column definitions */
  columns: TableColumn<T>[];
  /** Table data */
  data: T[];
  /** Key field for row identification */
  keyField: string;
  /** Row click handler */
  onRowClick?: (item: T) => void;
  /** Enable row selection */
  selectable?: boolean;
  /** Selected row IDs */
  selectedRows?: Set<string> | Record<string, boolean>;
  /** Selection change handler */
  onSelectionChange?: (selected: Record<string, boolean>) => void;
  /** Sorting mode: server uses listPageState, client uses DataTable internal sort */
  sortMode?: 'server' | 'client';

  // ===== State from useListPage =====
  /** State from useListPage hook */
  listPageState: UseListPageReturn<TSortField>;

  // ===== Data Fetching State =====
  /** Loading state */
  loading?: boolean;
  /** Error state */
  error?: Error | { message?: string } | null;
  /** Retry handler for error state */
  onRetry?: () => void;
  /** Total items count for pagination */
  total?: number;

  // ===== Empty State =====
  /** Empty state configuration */
  emptyState?: EmptyStateConfig;

  // ===== Content Slots =====
  /** Content before filters */
  beforeFilters?: React.ReactNode;
  /** Content after filters */
  afterFilters?: React.ReactNode;
  /** Content before table */
  beforeTable?: React.ReactNode;
  /** Content after table */
  afterTable?: React.ReactNode;

  // ===== Styling =====
  /** Additional class name */
  className?: string;
}

// =============================================================================
// COMPONENT
// =============================================================================

/**
 * Template component for list/table pages.
 *
 * Combines PageHeader, filters, DataTable, and Pagination into a consistent
 * layout that works with the useListPage hook.
 *
 * @example
 * const listPage = useListPage({ persistKey: 'books.suppliers' });
 * const { data, isLoading, error, mutate } = useAccountingSuppliers(listPage.buildApiParams());
 *
 * <ListPageTemplate
 *   module="books"
 *   title="Suppliers"
 *   icon={Building}
 *   primaryAction={{ label: 'Add Supplier', href: '/books/suppliers/new', icon: Plus }}
 *   columns={getSuppliersColumns()}
 *   data={data?.suppliers || []}
 *   keyField="id"
 *   listPageState={listPage}
 *   loading={isLoading}
 *   error={error}
 *   onRetry={mutate}
 *   total={data?.total}
 *   sortMode="server"
 *   filterInputs={[
 *     { name: 'search', type: 'text', placeholder: 'Search suppliers...' },
 *     { name: 'status', type: 'select', options: STATUS_OPTIONS },
 *   ]}
 * />
 */
export function ListPageTemplate<
  T extends Record<string, unknown>,
  TSortField extends string = string
>({
  // Module
  module,

  // Header
  title,
  subtitle,
  icon,
  breadcrumbs,

  // Actions
  primaryAction,
  secondaryActions,

  // Summary
  summaryCards,
  summaryColumns = 4,

  // Filters
  filterInputs,
  showSearch = true,
  searchPlaceholder = 'Search...',
  showClearFilters = true,
  customFilters,

  // Table
  columns,
  data,
  keyField,
  onRowClick,
  selectable,
  selectedRows,
  onSelectionChange,
  sortMode = 'server',

  // State
  listPageState,

  // Data fetching
  loading = false,
  error,
  onRetry,
  total = 0,

  // Empty state
  emptyState,

  // Slots
  beforeFilters,
  afterFilters,
  beforeTable,
  afterTable,

  // Styling
  className,
}: ListPageTemplateProps<T>) {
  const {
    pagination,
    filters,
    setFilter,
    clearFilters,
    hasActiveFilters,
    sortField,
    sortOrder,
    setSort,
  } = listPageState;

  const isServerSort = sortMode === 'server';

  // ===== Render Actions =====
  const renderActions = () => (
    <div className="flex items-center gap-3">
      {secondaryActions}
      {primaryAction && (
        primaryAction.href ? (
          <LinkButton
            href={primaryAction.href}
            variant="primary"
            module={module}
            icon={primaryAction.icon}
          >
            {primaryAction.label}
          </LinkButton>
        ) : (
          <Button
            onClick={primaryAction.onClick}
            variant="primary"
            module={module}
            icon={primaryAction.icon}
          >
            {primaryAction.label}
          </Button>
        )
      )}
    </div>
  );

  // ===== Render Summary Cards =====
  const renderSummaryCards = () => {
    if (!summaryCards || summaryCards.length === 0) return null;

    return (
      <StatGrid columns={summaryColumns} className="mb-6">
        {summaryCards.map((card, idx) => (
          <StatCard
            key={idx}
            title={card.label}
            value={card.value}
            icon={card.icon}
            variant={card.variant}
            colorClass={card.colorClass}
            subtitle={card.subtitle}
          />
        ))}
      </StatGrid>
    );
  };

  // ===== Render Filter Input =====
  const renderFilterInput = (config: FilterInputConfig) => {
    const { name, type, label, placeholder, options, className: inputClassName } = config;

    switch (type) {
      case 'text':
        return (
          <div key={name} className={cn('flex-1 min-w-[200px]', inputClassName)}>
            {label && <label className="block text-xs text-slate-muted mb-1">{label}</label>}
            <FilterInput
              type="text"
              value={(filters[name] as string) || ''}
              onChange={(e) => setFilter(name, e.target.value)}
              placeholder={placeholder}
              className="w-full"
            />
          </div>
        );

      case 'select':
        return (
          <div key={name} className={cn('min-w-[150px]', inputClassName)}>
            {label && <label className="block text-xs text-slate-muted mb-1">{label}</label>}
            <FilterSelect
              value={(filters[name] as string) || ''}
              onChange={(e) => setFilter(name, e.target.value)}
              className="w-full"
            >
              {options?.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </FilterSelect>
          </div>
        );

      case 'date':
        return (
          <div key={name} className={cn('min-w-[150px]', inputClassName)}>
            {label && <label className="block text-xs text-slate-muted mb-1">{label}</label>}
            <FilterInput
              type="date"
              value={(filters[name] as string) || ''}
              onChange={(e) => setFilter(name, e.target.value)}
              className="w-full"
            />
          </div>
        );

      default:
        return null;
    }
  };

  // ===== Render Filters =====
  const renderFilters = () => {
    const hasFilters = showSearch || (filterInputs && filterInputs.length > 0) || customFilters;
    if (!hasFilters) return null;

    return (
      <FilterCard
        title="Filters"
        icon={Filter}
        actions={
          showClearFilters && hasActiveFilters ? (
            <Button variant="ghost" size="sm" onClick={clearFilters} icon={X}>
              Clear
            </Button>
          ) : undefined
        }
        contentClassName="flex flex-wrap items-end gap-4"
      >
        {showSearch && (
          <div className="flex-1 min-w-[250px]">
            <SearchInput
              value={(filters.search as string) || ''}
              onChange={(value) => setFilter('search', value)}
              placeholder={searchPlaceholder}
            />
          </div>
        )}
        {customFilters || filterInputs?.map(renderFilterInput)}
      </FilterCard>
    );
  };

  // ===== Render Content (Table/Loading/Error/Empty) =====
  const renderContent = () => {
    // Error state
    if (error) {
      return (
        <ErrorState
          message={error instanceof Error ? error.message : error?.message || 'Something went wrong'}
          onRetry={onRetry}
        />
      );
    }

    // Loading state
    if (loading) {
      return <LoadingState message={`Loading ${title.toLowerCase()}...`} />;
    }

    // Empty state
    if (!data || data.length === 0) {
      return (
        <EmptyState
          title={emptyState?.title || `No ${title.toLowerCase()} found`}
          description={emptyState?.description || `Try adjusting your filters or create a new one.`}
          icon={emptyState?.icon || icon}
          action={emptyState?.action}
        />
      );
    }

    // Data table
    return (
      <>
        <DataTable
          columns={columns}
          data={data}
          keyField={keyField}
          onRowClick={onRowClick}
          selectable={selectable}
          selectedRowIds={selectedRows}
          onSelectChange={onSelectionChange}
          sortKey={isServerSort ? (sortField || undefined) : undefined}
          sortDir={isServerSort ? sortOrder : undefined}
          onSortChange={
            isServerSort ? (key, dir) => setSort(key as TSortField, dir) : undefined
          }
          manualSort={isServerSort}
        />
        {total > pagination.pageSize && (
          <div className="mt-4">
            <Pagination
              total={total}
              limit={pagination.pageSize}
              offset={pagination.offset}
              onPageChange={pagination.onPageChange}
              onLimitChange={pagination.onLimitChange}
              limitOptions={pagination.pageSizeOptions}
            />
          </div>
        )}
      </>
    );
  };

  // ===== Main Render =====
  return (
    <div className={cn('space-y-6', className)}>
      {/* Page Header */}
      <PageHeader
        title={title}
        subtitle={subtitle}
        icon={icon}
        breadcrumbs={breadcrumbs}
        actions={renderActions()}
      />

      {/* Summary Cards */}
      {renderSummaryCards()}

      {/* Before Filters Slot */}
      {beforeFilters}

      {/* Filters */}
      {renderFilters()}

      {/* After Filters Slot */}
      {afterFilters}

      {/* Before Table Slot */}
      {beforeTable}

      {/* Content (Table/Loading/Error/Empty) */}
      {renderContent()}

      {/* After Table Slot */}
      {afterTable}
    </div>
  );
}
