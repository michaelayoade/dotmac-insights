'use client';

import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Calendar, ChevronDown, Check, X, Search } from 'lucide-react';
import type { LineItemColumn, SelectOption } from './types';

// =============================================================================
// LINE ITEM ROW CELL
// =============================================================================

export interface LineItemRowProps<T extends Record<string, unknown>> {
  /** Column definition */
  column: LineItemColumn<T>;
  /** Current value */
  value: unknown;
  /** Full row data */
  row: T;
  /** Row index */
  rowIndex: number;
  /** All rows */
  allRows: T[];
  /** Change handler */
  onChange: (value: unknown) => void;
  /** Read-only mode */
  readOnly?: boolean;
  /** Error message */
  error?: string;
}

export function LineItemRow<T extends Record<string, unknown>>({
  column,
  value,
  row,
  rowIndex,
  allRows,
  onChange,
  readOnly = false,
  error,
}: LineItemRowProps<T>) {
  // Use custom render if provided
  if (column.render) {
    return (
      <td
        className={cn(
          'px-3 py-2',
          column.align === 'center' && 'text-center',
          column.align === 'right' && 'text-right',
          column.className
        )}
      >
        {column.render(value, row, rowIndex, onChange)}
      </td>
    );
  }

  // Render based on column type
  const cellContent = () => {
    switch (column.type) {
      case 'text':
        return (
          <TextCell
            value={value as string}
            onChange={onChange}
            readOnly={readOnly}
            placeholder={column.placeholder}
            error={!!error}
          />
        );

      case 'number':
        return (
          <NumberCell
            value={value as number}
            onChange={onChange}
            readOnly={readOnly}
            min={column.min}
            max={column.max}
            step={column.step}
            placeholder={column.placeholder}
            error={!!error}
          />
        );

      case 'currency':
        return (
          <CurrencyCell
            value={value as number}
            onChange={onChange}
            readOnly={readOnly}
            currency={column.currency || 'USD'}
            min={column.min}
            max={column.max}
            placeholder={column.placeholder}
            error={!!error}
          />
        );

      case 'select':
        return (
          <SelectCell
            value={value as string | number}
            onChange={onChange}
            options={column.options || []}
            readOnly={readOnly}
            placeholder={column.placeholder}
            error={!!error}
          />
        );

      case 'date':
        return (
          <DateCell
            value={value as string}
            onChange={onChange}
            readOnly={readOnly}
            error={!!error}
          />
        );

      case 'checkbox':
        return (
          <CheckboxCell
            value={value as boolean}
            onChange={onChange}
            readOnly={readOnly}
          />
        );

      case 'entity':
        return (
          <EntityCell
            value={value}
            onChange={onChange}
            entityType={column.entityType || 'generic'}
            readOnly={readOnly}
            placeholder={column.placeholder}
            error={!!error}
          />
        );

      case 'readonly':
      default:
        return (
          <ReadonlyCell
            value={value}
            format={column.format ? (v) => column.format!(v, row) : undefined}
          />
        );
    }
  };

  return (
    <td
      className={cn(
        'px-3 py-1.5',
        column.align === 'center' && 'text-center',
        column.align === 'right' && 'text-right',
        error && 'bg-coral-alert/5',
        column.className
      )}
      title={error}
    >
      {cellContent()}
    </td>
  );
}

// =============================================================================
// CELL TYPES
// =============================================================================

// Text Input Cell
interface TextCellProps {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  placeholder?: string;
  error?: boolean;
}

function TextCell({ value, onChange, readOnly, placeholder, error }: TextCellProps) {
  if (readOnly) {
    return <span className="text-sm">{value || '-'}</span>;
  }

  return (
    <input
      type="text"
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={cn(
        'w-full px-2 py-1 text-sm bg-transparent border rounded',
        'border-slate-border focus:border-teal-electric focus:outline-none',
        'placeholder:text-slate-muted',
        error && 'border-coral-alert'
      )}
    />
  );
}

// Number Input Cell
interface NumberCellProps {
  value: number;
  onChange: (value: number) => void;
  readOnly?: boolean;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  error?: boolean;
}

function NumberCell({ value, onChange, readOnly, min, max, step = 1, placeholder, error }: NumberCellProps) {
  if (readOnly) {
    return <span className="text-sm font-mono">{value?.toLocaleString() ?? '-'}</span>;
  }

  return (
    <input
      type="number"
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value ? parseFloat(e.target.value) : 0)}
      min={min}
      max={max}
      step={step}
      placeholder={placeholder}
      className={cn(
        'w-full px-2 py-1 text-sm bg-transparent border rounded text-right font-mono',
        'border-slate-border focus:border-teal-electric focus:outline-none',
        'placeholder:text-slate-muted',
        '[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none',
        error && 'border-coral-alert'
      )}
    />
  );
}

// Currency Input Cell
interface CurrencyCellProps {
  value: number;
  onChange: (value: number) => void;
  readOnly?: boolean;
  currency?: string;
  min?: number;
  max?: number;
  placeholder?: string;
  error?: boolean;
}

function CurrencyCell({ value, onChange, readOnly, currency = 'USD', min, max, placeholder, error }: CurrencyCellProps) {
  const [inputValue, setInputValue] = useState<string>(value?.toString() || '');

  useEffect(() => {
    if (!document.activeElement?.classList.contains('currency-input')) {
      setInputValue(value?.toString() || '');
    }
  }, [value]);

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
    }).format(val);
  };

  if (readOnly) {
    return <span className="text-sm font-mono">{value != null ? formatCurrency(value) : '-'}</span>;
  }

  const handleBlur = () => {
    const parsed = parseFloat(inputValue.replace(/[^0-9.-]/g, ''));
    if (!isNaN(parsed)) {
      let finalValue = parsed;
      if (min !== undefined) finalValue = Math.max(min, finalValue);
      if (max !== undefined) finalValue = Math.min(max, finalValue);
      onChange(finalValue);
      setInputValue(finalValue.toString());
    } else {
      setInputValue(value?.toString() || '');
    }
  };

  return (
    <div className="relative">
      <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-slate-muted">$</span>
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onBlur={handleBlur}
        placeholder={placeholder}
        className={cn(
          'currency-input w-full pl-5 pr-2 py-1 text-sm bg-transparent border rounded text-right font-mono',
          'border-slate-border focus:border-teal-electric focus:outline-none',
          'placeholder:text-slate-muted',
          error && 'border-coral-alert'
        )}
      />
    </div>
  );
}

// Select Cell
interface SelectCellProps {
  value: string | number;
  onChange: (value: string | number) => void;
  options: SelectOption[];
  readOnly?: boolean;
  placeholder?: string;
  error?: boolean;
}

function SelectCell({ value, onChange, options, readOnly, placeholder, error }: SelectCellProps) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => opt.value === value);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (readOnly) {
    return <span className="text-sm">{selectedOption?.label || '-'}</span>;
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'w-full px-2 py-1 text-sm bg-transparent border rounded text-left flex items-center justify-between gap-2',
          'border-slate-border hover:border-slate-muted focus:border-teal-electric focus:outline-none',
          error && 'border-coral-alert'
        )}
      >
        <span className={cn(!selectedOption && 'text-slate-muted')}>
          {selectedOption?.label || placeholder || 'Select...'}
        </span>
        <ChevronDown className="w-3.5 h-3.5 text-slate-muted" />
      </button>

      {isOpen && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-background border border-slate-border rounded-md shadow-lg max-h-48 overflow-auto">
          {options.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => {
                onChange(opt.value);
                setIsOpen(false);
              }}
              className={cn(
                'w-full px-3 py-1.5 text-sm text-left hover:bg-slate-elevated flex items-center justify-between',
                opt.value === value && 'bg-teal-electric/10 text-teal-electric'
              )}
            >
              {opt.label}
              {opt.value === value && <Check className="w-3.5 h-3.5" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Date Cell
interface DateCellProps {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  error?: boolean;
}

function DateCell({ value, onChange, readOnly, error }: DateCellProps) {
  if (readOnly) {
    const formatted = value ? new Date(value).toLocaleDateString() : '-';
    return <span className="text-sm">{formatted}</span>;
  }

  return (
    <div className="relative">
      <input
        type="date"
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          'w-full px-2 py-1 text-sm bg-transparent border rounded',
          'border-slate-border focus:border-teal-electric focus:outline-none',
          error && 'border-coral-alert'
        )}
      />
      <Calendar className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-muted pointer-events-none" />
    </div>
  );
}

// Checkbox Cell
interface CheckboxCellProps {
  value: boolean;
  onChange: (value: boolean) => void;
  readOnly?: boolean;
}

function CheckboxCell({ value, onChange, readOnly }: CheckboxCellProps) {
  return (
    <label className="flex items-center justify-center cursor-pointer">
      <input
        type="checkbox"
        checked={value || false}
        onChange={(e) => onChange(e.target.checked)}
        disabled={readOnly}
        className={cn(
          'w-4 h-4 rounded border-slate-border text-teal-electric focus:ring-teal-electric focus:ring-offset-0',
          readOnly && 'cursor-not-allowed opacity-50'
        )}
      />
    </label>
  );
}

// Entity Cell (for entity picker integration)
interface EntityCellProps {
  value: unknown;
  onChange: (value: unknown) => void;
  entityType: string;
  readOnly?: boolean;
  placeholder?: string;
  error?: boolean;
}

function EntityCell({ value, onChange, entityType, readOnly, placeholder, error }: EntityCellProps) {
  const [isSearching, setIsSearching] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Entity value should have id and name/label
  const entityValue = value as { id: string | number; name?: string; label?: string } | null;
  const displayName = entityValue?.name || entityValue?.label || '';

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsSearching(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (readOnly) {
    return <span className="text-sm">{displayName || '-'}</span>;
  }

  return (
    <div ref={ref} className="relative">
      <div
        className={cn(
          'w-full px-2 py-1 text-sm bg-transparent border rounded flex items-center justify-between gap-2 cursor-pointer',
          'border-slate-border hover:border-slate-muted',
          error && 'border-coral-alert'
        )}
        onClick={() => setIsSearching(true)}
      >
        <span className={cn('truncate', !displayName && 'text-slate-muted')}>
          {displayName || placeholder || `Select ${entityType}...`}
        </span>
        <div className="flex items-center gap-1">
          {entityValue && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onChange(null);
              }}
              className="p-0.5 hover:bg-slate-elevated rounded"
            >
              <X className="w-3 h-3 text-slate-muted" />
            </button>
          )}
          <Search className="w-3.5 h-3.5 text-slate-muted" />
        </div>
      </div>

      {isSearching && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-background border border-slate-border rounded-md shadow-lg p-3">
          <p className="text-xs text-slate-muted mb-2">
            Entity picker for: {entityType}
          </p>
          <p className="text-xs text-slate-muted">
            (Integrate with EntitySearch component)
          </p>
          <button
            type="button"
            onClick={() => setIsSearching(false)}
            className="mt-2 text-xs text-teal-electric hover:underline"
          >
            Close
          </button>
        </div>
      )}
    </div>
  );
}

// Readonly Cell
interface ReadonlyCellProps {
  value: unknown;
  format?: (value: unknown) => string;
}

function ReadonlyCell({ value, format }: ReadonlyCellProps) {
  const displayValue = format ? format(value) : String(value ?? '-');
  return <span className="text-sm text-slate-muted">{displayValue}</span>;
}

export default LineItemRow;
