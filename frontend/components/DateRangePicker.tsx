'use client';

import { useState, useRef, useEffect } from 'react';
import { Calendar, ChevronDown, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface DateRange {
  startDate: Date | null;
  endDate: Date | null;
}

interface DateRangePickerProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
  className?: string;
}

type PresetKey = 'today' | 'last7' | 'last30' | 'thisMonth' | 'lastMonth' | 'thisYear' | 'custom';

interface Preset {
  label: string;
  getRange: () => DateRange;
}

const presets: Record<PresetKey, Preset> = {
  today: {
    label: 'Today',
    getRange: () => {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const endOfDay = new Date(today);
      endOfDay.setHours(23, 59, 59, 999);
      return { startDate: today, endDate: endOfDay };
    },
  },
  last7: {
    label: 'Last 7 days',
    getRange: () => {
      const end = new Date();
      end.setHours(23, 59, 59, 999);
      const start = new Date();
      start.setDate(start.getDate() - 6);
      start.setHours(0, 0, 0, 0);
      return { startDate: start, endDate: end };
    },
  },
  last30: {
    label: 'Last 30 days',
    getRange: () => {
      const end = new Date();
      end.setHours(23, 59, 59, 999);
      const start = new Date();
      start.setDate(start.getDate() - 29);
      start.setHours(0, 0, 0, 0);
      return { startDate: start, endDate: end };
    },
  },
  thisMonth: {
    label: 'This month',
    getRange: () => {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), 1);
      const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
      end.setHours(23, 59, 59, 999);
      return { startDate: start, endDate: end };
    },
  },
  lastMonth: {
    label: 'Last month',
    getRange: () => {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const end = new Date(now.getFullYear(), now.getMonth(), 0);
      end.setHours(23, 59, 59, 999);
      return { startDate: start, endDate: end };
    },
  },
  thisYear: {
    label: 'This year',
    getRange: () => {
      const now = new Date();
      const start = new Date(now.getFullYear(), 0, 1);
      const end = new Date();
      end.setHours(23, 59, 59, 999);
      return { startDate: start, endDate: end };
    },
  },
  custom: {
    label: 'Custom range',
    getRange: () => ({ startDate: null, endDate: null }),
  },
};

function formatDate(date: Date | null): string {
  if (!date) return '';
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function formatDateInput(date: Date | null): string {
  if (!date) return '';
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function parseInputDate(value: string): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return isNaN(date.getTime()) ? null : date;
}

function getActivePreset(range: DateRange): PresetKey | null {
  if (!range.startDate || !range.endDate) return null;

  for (const [key, preset] of Object.entries(presets)) {
    if (key === 'custom') continue;
    const presetRange = preset.getRange();
    if (
      presetRange.startDate &&
      presetRange.endDate &&
      presetRange.startDate.toDateString() === range.startDate.toDateString() &&
      presetRange.endDate.toDateString() === range.endDate.toDateString()
    ) {
      return key as PresetKey;
    }
  }
  return 'custom';
}

export function DateRangePicker({ value, onChange, className }: DateRangePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [showCustom, setShowCustom] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const activePreset = getActivePreset(value);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handlePresetClick = (key: PresetKey) => {
    if (key === 'custom') {
      setShowCustom(true);
    } else {
      const range = presets[key].getRange();
      onChange(range);
      setShowCustom(false);
      setIsOpen(false);
    }
  };

  const handleCustomChange = (field: 'startDate' | 'endDate', dateValue: string) => {
    const date = parseInputDate(dateValue);
    if (field === 'startDate' && date) {
      date.setHours(0, 0, 0, 0);
    }
    if (field === 'endDate' && date) {
      date.setHours(23, 59, 59, 999);
    }
    onChange({
      ...value,
      [field]: date,
    });
  };

  const handleClear = () => {
    onChange({ startDate: null, endDate: null });
    setShowCustom(false);
    setIsOpen(false);
  };

  const displayLabel =
    value.startDate && value.endDate
      ? `${formatDate(value.startDate)} - ${formatDate(value.endDate)}`
      : 'Select date range';

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'flex items-center gap-2 px-4 py-2 rounded-lg transition-all',
          'bg-slate-elevated border border-slate-border',
          'text-sm font-medium',
          isOpen ? 'border-teal-electric/50 text-foreground' : 'text-slate-muted hover:text-foreground hover:border-slate-elevated',
          value.startDate && value.endDate && 'text-foreground'
        )}
      >
        <Calendar className="w-4 h-4" />
        <span className="max-w-[200px] truncate">{displayLabel}</span>
        <ChevronDown className={cn('w-4 h-4 transition-transform', isOpen && 'rotate-180')} />
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 z-50 min-w-[280px] bg-slate-card border border-slate-border rounded-xl shadow-2xl overflow-hidden">
          {/* Presets */}
          <div className="p-2 border-b border-slate-border">
            <div className="grid grid-cols-2 gap-1">
              {(Object.entries(presets) as [PresetKey, Preset][]).map(([key, preset]) => (
                <button
                  key={key}
                  onClick={() => handlePresetClick(key)}
                  className={cn(
                    'px-3 py-2 text-sm rounded-md transition-all text-left',
                    activePreset === key
                      ? 'bg-teal-electric/20 text-teal-electric'
                      : 'text-slate-muted hover:text-foreground hover:bg-slate-elevated'
                  )}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          {/* Custom Range Inputs */}
          {(showCustom || activePreset === 'custom') && (
            <div className="p-4 border-b border-slate-border space-y-3">
              <div>
                <label className="block text-xs text-slate-muted mb-1">Start Date</label>
                <input
                  type="date"
                  value={formatDateInput(value.startDate)}
                  onChange={(e) => handleCustomChange('startDate', e.target.value)}
                  className={cn(
                    'w-full px-3 py-2 rounded-lg text-sm',
                    'bg-slate-elevated border border-slate-border',
                    'text-foreground placeholder-slate-muted',
                    'focus:outline-none focus:border-teal-electric/50',
                    '[color-scheme:dark]'
                  )}
                />
              </div>
              <div>
                <label className="block text-xs text-slate-muted mb-1">End Date</label>
                <input
                  type="date"
                  value={formatDateInput(value.endDate)}
                  onChange={(e) => handleCustomChange('endDate', e.target.value)}
                  min={formatDateInput(value.startDate)}
                  className={cn(
                    'w-full px-3 py-2 rounded-lg text-sm',
                    'bg-slate-elevated border border-slate-border',
                    'text-foreground placeholder-slate-muted',
                    'focus:outline-none focus:border-teal-electric/50',
                    '[color-scheme:dark]'
                  )}
                />
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="p-2 flex items-center justify-between">
            <button
              onClick={handleClear}
              className="flex items-center gap-1 px-3 py-1.5 text-xs text-slate-muted hover:text-coral-alert transition-colors"
            >
              <X className="w-3 h-3" />
              Clear
            </button>
            <button
              onClick={() => setIsOpen(false)}
              className="px-4 py-1.5 text-xs font-medium bg-teal-electric/20 text-teal-electric rounded-md hover:bg-teal-electric/30 transition-colors"
            >
              Apply
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
