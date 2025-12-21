'use client';

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Search, X, Loader2, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface EntityOption {
  id: number | string;
  label: string;
  sublabel?: string;
}

interface EntitySearchProps {
  label?: string;
  placeholder?: string;
  value?: EntityOption | null;
  options?: EntityOption[];
  loading?: boolean;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
  onSelect: (option: EntityOption | null) => void;
  onSearch?: (query: string) => void;
  renderOption?: (option: EntityOption) => React.ReactNode;
  emptyMessage?: string;
  allowClear?: boolean;
}

export function EntitySearch({
  label,
  placeholder = 'Search...',
  value,
  options = [],
  loading = false,
  error,
  required = false,
  disabled = false,
  className,
  onSelect,
  onSearch,
  renderOption,
  emptyMessage = 'No results found',
  allowClear = true,
}: EntitySearchProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Filter options based on query (client-side filtering)
  const filteredOptions = useMemo(() => {
    if (!query || onSearch) return options;
    const lowerQuery = query.toLowerCase();
    return options.filter(
      (opt) =>
        opt.label.toLowerCase().includes(lowerQuery) ||
        opt.sublabel?.toLowerCase().includes(lowerQuery) ||
        String(opt.id).includes(lowerQuery)
    );
  }, [options, query, onSearch]);

  // Handle search with debounce for async search
  const handleQueryChange = useCallback(
    (newQuery: string) => {
      setQuery(newQuery);
      setHighlightedIndex(0);
      if (onSearch) {
        onSearch(newQuery);
      }
    },
    [onSearch]
  );

  // Handle option selection
  const handleSelect = useCallback(
    (option: EntityOption) => {
      onSelect(option);
      setQuery('');
      setIsOpen(false);
    },
    [onSelect]
  );

  // Clear selection
  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onSelect(null);
      setQuery('');
      inputRef.current?.focus();
    },
    [onSelect]
  );

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isOpen) {
        if (e.key === 'ArrowDown' || e.key === 'Enter') {
          setIsOpen(true);
        }
        return;
      }

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setHighlightedIndex((prev) =>
            prev < filteredOptions.length - 1 ? prev + 1 : 0
          );
          break;
        case 'ArrowUp':
          e.preventDefault();
          setHighlightedIndex((prev) =>
            prev > 0 ? prev - 1 : filteredOptions.length - 1
          );
          break;
        case 'Enter':
          e.preventDefault();
          if (filteredOptions[highlightedIndex]) {
            handleSelect(filteredOptions[highlightedIndex]);
          }
          break;
        case 'Escape':
          setIsOpen(false);
          setQuery('');
          break;
        case 'Tab':
          setIsOpen(false);
          break;
      }
    },
    [isOpen, filteredOptions, highlightedIndex, handleSelect]
  );

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setQuery('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Reset highlighted index when options change
  useEffect(() => {
    setHighlightedIndex(0);
  }, [filteredOptions.length]);

  const displayValue = value ? value.label : '';

  return (
    <div className={cn('space-y-1.5', className)} ref={containerRef}>
      {label && (
        <label className="block text-sm text-slate-muted">
          {label}
          {required && <span className="text-coral-alert ml-1">*</span>}
        </label>
      )}
      <div className="relative">
        <div
          className={cn(
            'flex items-center gap-2 w-full bg-slate-elevated border rounded-lg px-3 py-2 cursor-text',
            error ? 'border-red-500/60' : 'border-slate-border',
            disabled && 'opacity-50 cursor-not-allowed',
            isOpen && 'ring-2 ring-teal-electric/50'
          )}
          onClick={() => {
            if (!disabled) {
              setIsOpen(true);
              inputRef.current?.focus();
            }
          }}
        >
          <Search className="w-4 h-4 text-slate-muted flex-shrink-0" />
          {value && !isOpen ? (
            <div className="flex-1 flex items-center justify-between min-w-0">
              <span className="text-sm text-foreground truncate">{displayValue}</span>
              {allowClear && !disabled && (
                <button
                  type="button"
                  onClick={handleClear}
                  className="p-0.5 hover:bg-slate-card rounded"
                >
                  <X className="w-3.5 h-3.5 text-slate-muted hover:text-foreground" />
                </button>
              )}
            </div>
          ) : (
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => handleQueryChange(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsOpen(true)}
              placeholder={value ? displayValue : placeholder}
              disabled={disabled}
              className="flex-1 bg-transparent text-sm text-foreground placeholder:text-slate-muted focus:outline-none min-w-0"
            />
          )}
          {loading ? (
            <Loader2 className="w-4 h-4 text-slate-muted animate-spin flex-shrink-0" />
          ) : (
            <ChevronDown
              className={cn(
                'w-4 h-4 text-slate-muted flex-shrink-0 transition-transform',
                isOpen && 'rotate-180'
              )}
            />
          )}
        </div>

        {isOpen && (
          <div className="absolute z-50 w-full mt-1 bg-slate-card border border-slate-border rounded-lg shadow-lg max-h-60 overflow-auto">
            {loading && filteredOptions.length === 0 ? (
              <div className="px-3 py-4 text-sm text-slate-muted text-center flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading...
              </div>
            ) : filteredOptions.length === 0 ? (
              <div className="px-3 py-4 text-sm text-slate-muted text-center">
                {emptyMessage}
              </div>
            ) : (
              <ul className="py-1">
                {filteredOptions.map((option, index) => (
                  <li
                    key={option.id}
                    onClick={() => handleSelect(option)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    className={cn(
                      'px-3 py-2 cursor-pointer text-sm',
                      index === highlightedIndex
                        ? 'bg-slate-elevated text-foreground'
                        : 'text-slate-muted hover:bg-slate-elevated hover:text-foreground',
                      value?.id === option.id && 'bg-teal-electric/10 text-teal-electric'
                    )}
                  >
                    {renderOption ? (
                      renderOption(option)
                    ) : (
                      <div>
                        <div className="font-medium">{option.label}</div>
                        {option.sublabel && (
                          <div className="text-xs text-slate-muted">{option.sublabel}</div>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}

// Pre-configured variants for common entity types
export function CustomerSearch({
  customers,
  value,
  onSelect,
  loading,
  ...props
}: Omit<EntitySearchProps, 'options' | 'onSelect' | 'value'> & {
  customers: Array<{ id: number; name?: string; customer_name?: string; email?: string }>;
  value?: { id: number; name: string } | null;
  onSelect: (customer: { id: number; name: string } | null) => void;
}) {
  const options: EntityOption[] = useMemo(
    () =>
      customers.map((c) => ({
        id: c.id,
        label: c.name || c.customer_name || `Customer #${c.id}`,
        sublabel: c.email || `ID: ${c.id}`,
      })),
    [customers]
  );

  const selectedOption = value
    ? { id: value.id, label: value.name, sublabel: `ID: ${value.id}` }
    : null;

  return (
    <EntitySearch
      placeholder="Search customers..."
      options={options}
      value={selectedOption}
      loading={loading}
      onSelect={(opt) => {
        if (opt) {
          onSelect({ id: Number(opt.id), name: opt.label });
        } else {
          onSelect(null);
        }
      }}
      {...props}
    />
  );
}

export function SupplierSearch({
  suppliers,
  value,
  onSelect,
  loading,
  ...props
}: Omit<EntitySearchProps, 'options' | 'onSelect' | 'value'> & {
  suppliers: Array<{ id: number | string; name?: string; supplier_name?: string; email?: string }>;
  value?: { id: number | string; name: string } | null;
  onSelect: (supplier: { id: number | string; name: string } | null) => void;
}) {
  const options: EntityOption[] = useMemo(
    () =>
      suppliers.map((s) => ({
        id: s.id,
        label: s.name || s.supplier_name || `Supplier #${s.id}`,
        sublabel: s.email || `ID: ${s.id}`,
      })),
    [suppliers]
  );

  const selectedOption = value
    ? { id: value.id, label: value.name, sublabel: `ID: ${value.id}` }
    : null;

  return (
    <EntitySearch
      placeholder="Search suppliers..."
      options={options}
      value={selectedOption}
      loading={loading}
      onSelect={(opt) => {
        if (opt) {
          onSelect({ id: opt.id, name: opt.label });
        } else {
          onSelect(null);
        }
      }}
      {...props}
    />
  );
}

export function AccountSearch({
  accounts,
  value,
  onSelect,
  loading,
  ...props
}: Omit<EntitySearchProps, 'options' | 'onSelect' | 'value'> & {
  accounts: Array<{ id?: number; name: string; account_number?: string; account_type?: string }>;
  value?: { name: string; account_number?: string } | null;
  onSelect: (account: { name: string; account_number?: string } | null) => void;
}) {
  const options: EntityOption[] = useMemo(
    () =>
      accounts.map((a) => ({
        id: a.id || a.name,
        label: a.account_number ? `${a.account_number} - ${a.name}` : a.name,
        sublabel: a.account_type,
      })),
    [accounts]
  );

  const selectedOption = value
    ? {
        id: value.account_number || value.name,
        label: value.account_number ? `${value.account_number} - ${value.name}` : value.name,
      }
    : null;

  return (
    <EntitySearch
      placeholder="Search accounts..."
      options={options}
      value={selectedOption}
      loading={loading}
      onSelect={(opt) => {
        if (opt) {
          const parts = opt.label.split(' - ');
          onSelect({
            name: parts.length > 1 ? parts.slice(1).join(' - ') : opt.label,
            account_number: parts.length > 1 ? parts[0] : undefined,
          });
        } else {
          onSelect(null);
        }
      }}
      {...props}
    />
  );
}

export function EmployeeSearch({
  employees,
  value,
  onSelect,
  loading,
  ...props
}: Omit<EntitySearchProps, 'options' | 'onSelect' | 'value'> & {
  employees: Array<{ id: number; name?: string; employee_name?: string; department?: string; email?: string }>;
  value?: { id: number; name: string } | null;
  onSelect: (employee: { id: number; name: string } | null) => void;
}) {
  const options: EntityOption[] = useMemo(
    () =>
      employees.map((e) => ({
        id: e.id,
        label: e.name || e.employee_name || `Employee #${e.id}`,
        sublabel: e.department || e.email || `ID: ${e.id}`,
      })),
    [employees]
  );

  const selectedOption = value
    ? { id: value.id, label: value.name, sublabel: `ID: ${value.id}` }
    : null;

  return (
    <EntitySearch
      placeholder="Search employees..."
      options={options}
      value={selectedOption}
      loading={loading}
      onSelect={(opt) => {
        if (opt) {
          onSelect({ id: Number(opt.id), name: opt.label });
        } else {
          onSelect(null);
        }
      }}
      {...props}
    />
  );
}

export function InvoiceSearch({
  invoices,
  value,
  onSelect,
  loading,
  ...props
}: Omit<EntitySearchProps, 'options' | 'onSelect' | 'value'> & {
  invoices: Array<{ id: number; invoice_number?: string; customer_name?: string; total_amount?: number; currency?: string }>;
  value?: { id: number; invoice_number?: string } | null;
  onSelect: (invoice: { id: number; invoice_number?: string } | null) => void;
}) {
  const options: EntityOption[] = useMemo(
    () =>
      invoices.map((inv) => ({
        id: inv.id,
        label: inv.invoice_number || `Invoice #${inv.id}`,
        sublabel: inv.customer_name
          ? `${inv.customer_name}${inv.total_amount ? ` - ${inv.currency || 'NGN'} ${inv.total_amount.toLocaleString()}` : ''}`
          : `ID: ${inv.id}`,
      })),
    [invoices]
  );

  const selectedOption = value
    ? { id: value.id, label: value.invoice_number || `Invoice #${value.id}` }
    : null;

  return (
    <EntitySearch
      placeholder="Search invoices..."
      options={options}
      value={selectedOption}
      loading={loading}
      onSelect={(opt) => {
        if (opt) {
          onSelect({ id: Number(opt.id), invoice_number: opt.label });
        } else {
          onSelect(null);
        }
      }}
      {...props}
    />
  );
}

export function ItemSearch({
  items,
  value,
  onSelect,
  loading,
  ...props
}: Omit<EntitySearchProps, 'options' | 'onSelect' | 'value'> & {
  items: Array<{ id: number; item_code: string; item_name?: string; item_group?: string; stock_uom?: string; total_stock_qty?: number }>;
  value?: { id: number; item_code: string; item_name?: string } | null;
  onSelect: (item: { id: number; item_code: string; item_name?: string } | null) => void;
}) {
  const options: EntityOption[] = useMemo(
    () =>
      items.map((item) => ({
        id: item.id,
        label: item.item_code,
        sublabel: item.item_name
          ? `${item.item_name}${item.total_stock_qty !== undefined ? ` (${item.total_stock_qty} ${item.stock_uom || 'units'})` : ''}`
          : item.item_group || `ID: ${item.id}`,
      })),
    [items]
  );

  const selectedOption = value
    ? { id: value.id, label: value.item_code, sublabel: value.item_name }
    : null;

  return (
    <EntitySearch
      placeholder="Search items..."
      options={options}
      value={selectedOption}
      loading={loading}
      onSelect={(opt) => {
        if (opt) {
          const item = items.find((i) => i.id === Number(opt.id));
          onSelect({
            id: Number(opt.id),
            item_code: opt.label,
            item_name: item?.item_name,
          });
        } else {
          onSelect(null);
        }
      }}
      {...props}
    />
  );
}

export function WarehouseSearch({
  warehouses,
  value,
  onSelect,
  loading,
  ...props
}: Omit<EntitySearchProps, 'options' | 'onSelect' | 'value'> & {
  warehouses: Array<{ id: number; warehouse_name: string; parent_warehouse?: string; is_group?: boolean; company?: string }>;
  value?: { id: number; warehouse_name: string } | null;
  onSelect: (warehouse: { id: number; warehouse_name: string } | null) => void;
}) {
  const options: EntityOption[] = useMemo(
    () =>
      warehouses.map((wh) => ({
        id: wh.id,
        label: wh.warehouse_name,
        sublabel: wh.parent_warehouse
          ? `${wh.parent_warehouse}${wh.is_group ? ' (Group)' : ''}`
          : wh.company || (wh.is_group ? 'Group' : `ID: ${wh.id}`),
      })),
    [warehouses]
  );

  const selectedOption = value
    ? { id: value.id, label: value.warehouse_name }
    : null;

  return (
    <EntitySearch
      placeholder="Search warehouses..."
      options={options}
      value={selectedOption}
      loading={loading}
      onSelect={(opt) => {
        if (opt) {
          onSelect({ id: Number(opt.id), warehouse_name: opt.label });
        } else {
          onSelect(null);
        }
      }}
      {...props}
    />
  );
}

export function TeamSearch({
  teams,
  value,
  onSelect,
  loading,
  ...props
}: Omit<EntitySearchProps, 'options' | 'onSelect' | 'value'> & {
  teams: Array<{ id: number; name: string; description?: string; domain?: string; is_active?: boolean }>;
  value?: { id: number; name: string } | null;
  onSelect: (team: { id: number; name: string } | null) => void;
}) {
  const options: EntityOption[] = useMemo(
    () =>
      teams
        .filter((t) => t.is_active !== false)
        .map((t) => ({
          id: t.id,
          label: t.name,
          sublabel: t.domain || t.description || `ID: ${t.id}`,
        })),
    [teams]
  );

  const selectedOption = value
    ? { id: value.id, label: value.name, sublabel: `ID: ${value.id}` }
    : null;

  return (
    <EntitySearch
      placeholder="Search teams..."
      options={options}
      value={selectedOption}
      loading={loading}
      onSelect={(opt) => {
        if (opt) {
          onSelect({ id: Number(opt.id), name: opt.label });
        } else {
          onSelect(null);
        }
      }}
      {...props}
    />
  );
}

export function VehicleSearch({
  vehicles,
  value,
  onSelect,
  loading,
  ...props
}: Omit<EntitySearchProps, 'options' | 'onSelect' | 'value'> & {
  vehicles: Array<{ id: number; license_plate: string; make?: string; model?: string; driver_name?: string; is_active?: boolean }>;
  value?: { id: number; license_plate: string } | null;
  onSelect: (vehicle: { id: number; license_plate: string } | null) => void;
}) {
  const options: EntityOption[] = useMemo(
    () =>
      vehicles
        .filter((v) => v.is_active !== false)
        .map((v) => ({
          id: v.id,
          label: v.license_plate,
          sublabel: [v.make, v.model, v.driver_name ? `Driver: ${v.driver_name}` : null]
            .filter(Boolean)
            .join(' • ') || `ID: ${v.id}`,
        })),
    [vehicles]
  );

  const selectedOption = value
    ? { id: value.id, label: value.license_plate, sublabel: `ID: ${value.id}` }
    : null;

  return (
    <EntitySearch
      placeholder="Search vehicles..."
      options={options}
      value={selectedOption}
      loading={loading}
      onSelect={(opt) => {
        if (opt) {
          onSelect({ id: Number(opt.id), license_plate: opt.label });
        } else {
          onSelect(null);
        }
      }}
      {...props}
    />
  );
}

export function AssetSearch({
  assets,
  value,
  onSelect,
  loading,
  ...props
}: Omit<EntitySearchProps, 'options' | 'onSelect' | 'value'> & {
  assets: Array<{ id: number; asset_name: string; asset_code?: string; asset_category?: string; location?: string; status?: string }>;
  value?: { id: number; asset_name: string; asset_code?: string } | null;
  onSelect: (asset: { id: number; asset_name: string; asset_code?: string } | null) => void;
}) {
  const options: EntityOption[] = useMemo(
    () =>
      assets.map((a) => ({
        id: a.id,
        label: a.asset_code ? `${a.asset_code} - ${a.asset_name}` : a.asset_name,
        sublabel: [a.asset_category, a.location, a.status]
          .filter(Boolean)
          .join(' • ') || `ID: ${a.id}`,
      })),
    [assets]
  );

  const selectedOption = value
    ? {
        id: value.id,
        label: value.asset_code ? `${value.asset_code} - ${value.asset_name}` : value.asset_name,
        sublabel: `ID: ${value.id}`,
      }
    : null;

  return (
    <EntitySearch
      placeholder="Search assets..."
      options={options}
      value={selectedOption}
      loading={loading}
      onSelect={(opt) => {
        if (opt) {
          const asset = assets.find((a) => a.id === Number(opt.id));
          onSelect({
            id: Number(opt.id),
            asset_name: asset?.asset_name || opt.label,
            asset_code: asset?.asset_code,
          });
        } else {
          onSelect(null);
        }
      }}
      {...props}
    />
  );
}
