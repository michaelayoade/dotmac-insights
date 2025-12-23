'use client';

import { useState, useEffect } from 'react';
import {
  X,
  Target,
  Calendar,
  FileText,
  Loader2,
  Save,
} from 'lucide-react';
import type { Milestone, MilestoneStatus, MilestoneCreatePayload, MilestoneUpdatePayload } from '@/lib/api/domains/projects';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

interface MilestoneFormProps {
  milestone?: Milestone | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: MilestoneCreatePayload | MilestoneUpdatePayload) => Promise<void>;
}

const statusOptions: { value: MilestoneStatus; label: string }[] = [
  { value: 'planned', label: 'Planned' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'on_hold', label: 'On Hold' },
];

export function MilestoneForm({ milestone, isOpen, onClose, onSubmit }: MilestoneFormProps) {
  const isEdit = !!milestone;

  const [formData, setFormData] = useState<MilestoneCreatePayload>({
    name: '',
    description: '',
    status: 'planned',
    planned_start_date: null,
    planned_end_date: null,
    actual_start_date: null,
    actual_end_date: null,
    percent_complete: 0,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when milestone changes
  useEffect(() => {
    if (milestone) {
      setFormData({
        name: milestone.name,
        description: milestone.description || '',
        status: milestone.status,
        planned_start_date: milestone.planned_start_date || null,
        planned_end_date: milestone.planned_end_date || null,
        actual_start_date: milestone.actual_start_date || null,
        actual_end_date: milestone.actual_end_date || null,
        percent_complete: milestone.percent_complete || 0,
      });
    } else {
      setFormData({
        name: '',
        description: '',
        status: 'planned',
        planned_start_date: null,
        planned_end_date: null,
        actual_start_date: null,
        actual_end_date: null,
        percent_complete: 0,
      });
    }
    setError(null);
  }, [milestone, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setError('Milestone name is required');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await onSubmit(formData);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save milestone');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-slate-card border border-slate-border rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-border">
          <div className="flex items-center gap-3">
            <Target className="w-5 h-5 text-teal-electric" />
            <h2 className="text-lg font-semibold text-foreground">
              {isEdit ? 'Edit Milestone' : 'Create Milestone'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-muted hover:text-foreground hover:bg-slate-elevated transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-140px)]">
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Name <span className="text-red-400">*</span>
            </label>
            <div className="relative">
              <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder-slate-muted focus:border-teal-electric focus:ring-1 focus:ring-teal-electric outline-none transition-colors"
                placeholder="Milestone name"
                required
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Description
            </label>
            <div className="relative">
              <FileText className="absolute left-3 top-3 w-4 h-4 text-slate-muted" />
              <textarea
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder-slate-muted focus:border-teal-electric focus:ring-1 focus:ring-teal-electric outline-none transition-colors resize-none"
                placeholder="Describe this milestone..."
              />
            </div>
          </div>

          {/* Status */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Status
            </label>
            <select
              value={formData.status}
              onChange={(e) => setFormData({ ...formData, status: e.target.value as MilestoneStatus })}
              className="w-full px-4 py-2.5 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:border-teal-electric focus:ring-1 focus:ring-teal-electric outline-none transition-colors"
            >
              {statusOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Dates Row */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">
                Planned Start
              </label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
                <input
                  type="date"
                  value={formData.planned_start_date || ''}
                  onChange={(e) => setFormData({ ...formData, planned_start_date: e.target.value || null })}
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:border-teal-electric focus:ring-1 focus:ring-teal-electric outline-none transition-colors"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">
                Planned End
              </label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
                <input
                  type="date"
                  value={formData.planned_end_date || ''}
                  onChange={(e) => setFormData({ ...formData, planned_end_date: e.target.value || null })}
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:border-teal-electric focus:ring-1 focus:ring-teal-electric outline-none transition-colors"
                />
              </div>
            </div>
          </div>

          {/* Actual Dates (shown in edit mode) */}
          {isEdit && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">
                  Actual Start
                </label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
                  <input
                    type="date"
                    value={formData.actual_start_date || ''}
                    onChange={(e) => setFormData({ ...formData, actual_start_date: e.target.value || null })}
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:border-teal-electric focus:ring-1 focus:ring-teal-electric outline-none transition-colors"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">
                  Actual End
                </label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
                  <input
                    type="date"
                    value={formData.actual_end_date || ''}
                    onChange={(e) => setFormData({ ...formData, actual_end_date: e.target.value || null })}
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:border-teal-electric focus:ring-1 focus:ring-teal-electric outline-none transition-colors"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Progress (edit mode) */}
          {isEdit && (
            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">
                Progress ({formData.percent_complete}%)
              </label>
              <input
                type="range"
                min={0}
                max={100}
                value={formData.percent_complete || 0}
                onChange={(e) => setFormData({ ...formData, percent_complete: Number(e.target.value) })}
                className="w-full h-2 bg-slate-elevated rounded-lg appearance-none cursor-pointer accent-teal-electric"
              />
            </div>
          )}
        </form>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-border bg-slate-elevated/50">
          <Button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors"
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            className={cn(
              'px-4 py-2 rounded-lg font-semibold transition-colors inline-flex items-center gap-2',
              isSubmitting
                ? 'bg-slate-elevated text-slate-muted cursor-not-allowed'
                : 'bg-teal-electric text-slate-950 hover:bg-teal-electric/90'
            )}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                {isEdit ? 'Update' : 'Create'}
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default MilestoneForm;
