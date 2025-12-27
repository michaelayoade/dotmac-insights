'use client';

import { useState } from 'react';
import {
  Target,
  Plus,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Flag,
} from 'lucide-react';
import type { Milestone, MilestoneStatus, MilestoneCreatePayload, MilestoneUpdatePayload } from '@/lib/api/domains/projects';
import { useProjectMilestones, useMilestoneMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';
import { MilestoneCard } from './MilestoneCard';
import { MilestoneForm } from './MilestoneForm';

interface MilestoneListProps {
  projectId: number;
  onTaskClick?: (taskId: number) => void;
}

// Status filter options
const statusFilters: { value: MilestoneStatus | 'all'; label: string; count?: (m: Milestone[]) => number }[] = [
  { value: 'all', label: 'All' },
  { value: 'planned', label: 'Planned' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'on_hold', label: 'On Hold' },
];

export function MilestoneList({ projectId, onTaskClick }: MilestoneListProps) {
  const [statusFilter, setStatusFilter] = useState<MilestoneStatus | 'all'>('all');
  const [formOpen, setFormOpen] = useState(false);
  const [editingMilestone, setEditingMilestone] = useState<Milestone | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<Milestone | null>(null);

  const { data, isLoading, error, mutate } = useProjectMilestones(
    projectId,
    statusFilter === 'all' ? undefined : statusFilter
  );
  const { createMilestone, updateMilestone, deleteMilestone } = useMilestoneMutations();

  const milestones: Milestone[] = data?.data || [];

  // Calculate stats
  const stats = {
    total: milestones.length,
    completed: milestones.filter((m) => m.status === 'completed').length,
    inProgress: milestones.filter((m) => m.status === 'in_progress').length,
    overdue: milestones.filter((m) => m.is_overdue && m.status !== 'completed').length,
  };

  const handleCreate = async (payload: MilestoneCreatePayload | MilestoneUpdatePayload) => {
    await createMilestone(projectId, payload as MilestoneCreatePayload);
    mutate();
  };

  const handleUpdate = async (payload: MilestoneCreatePayload | MilestoneUpdatePayload) => {
    if (editingMilestone) {
      await updateMilestone(editingMilestone.id, payload as MilestoneUpdatePayload, projectId);
      mutate();
    }
  };

  const handleDelete = async () => {
    if (deleteConfirm) {
      await deleteMilestone(deleteConfirm.id, projectId);
      setDeleteConfirm(null);
      mutate();
    }
  };

  const openEditForm = (milestone: Milestone) => {
    setEditingMilestone(milestone);
    setFormOpen(true);
  };

  const openCreateForm = () => {
    setEditingMilestone(null);
    setFormOpen(true);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-teal-electric animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load milestones</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h3 className="text-foreground font-semibold flex items-center gap-2">
            <Target className="w-5 h-5 text-teal-electric" />
            Milestones ({stats.total})
          </h3>
          {/* Stats Pills */}
          <div className="flex items-center gap-2 text-xs">
            {stats.completed > 0 && (
              <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-green-500/10 text-green-400">
                <CheckCircle2 className="w-3 h-3" />
                {stats.completed} done
              </span>
            )}
            {stats.inProgress > 0 && (
              <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-blue-500/10 text-blue-400">
                <Clock className="w-3 h-3" />
                {stats.inProgress} active
              </span>
            )}
            {stats.overdue > 0 && (
              <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-red-500/10 text-red-400">
                <AlertTriangle className="w-3 h-3" />
                {stats.overdue} overdue
              </span>
            )}
          </div>
        </div>
        <Button
          onClick={openCreateForm}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Milestone
        </Button>
      </div>

      {/* Status Filter */}
      <div className="flex items-center gap-1 p-1 bg-slate-elevated rounded-lg w-fit">
        {statusFilters.map((filter) => (
          <button
            key={filter.value}
            onClick={() => setStatusFilter(filter.value)}
            className={cn(
              'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
              statusFilter === filter.value
                ? 'bg-slate-card text-foreground shadow-sm'
                : 'text-slate-muted hover:text-foreground'
            )}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {/* Milestone Cards */}
      {milestones.length > 0 ? (
        <div className="space-y-3">
          {milestones.map((milestone) => (
            <MilestoneCard
              key={milestone.id}
              milestone={milestone}
              onEdit={openEditForm}
              onDelete={setDeleteConfirm}
              onTaskClick={onTaskClick}
            />
          ))}
        </div>
      ) : (
        <div className="bg-slate-card border border-slate-border rounded-xl p-12 text-center">
          <Flag className="w-12 h-12 text-slate-muted/50 mx-auto mb-4" />
          <h4 className="text-foreground font-semibold mb-2">No milestones yet</h4>
          <p className="text-slate-muted text-sm mb-4">
            Create milestones to track key deliverables and progress
          </p>
          <Button
            onClick={openCreateForm}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-teal-electric text-teal-electric hover:bg-teal-electric/10 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create First Milestone
          </Button>
        </div>
      )}

      {/* Create/Edit Form Modal */}
      <MilestoneForm
        milestone={editingMilestone}
        isOpen={formOpen}
        onClose={() => {
          setFormOpen(false);
          setEditingMilestone(null);
        }}
        onSubmit={editingMilestone ? handleUpdate : handleCreate}
      />

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setDeleteConfirm(null)} />
          <div className="relative bg-slate-card border border-slate-border rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-full bg-red-500/10">
                <AlertTriangle className="w-6 h-6 text-red-400" />
              </div>
              <div>
                <h3 className="text-foreground font-semibold">Delete Milestone</h3>
                <p className="text-slate-muted text-sm">This action cannot be undone</p>
              </div>
            </div>
            <p className="text-foreground mb-6">
              Are you sure you want to delete <span className="font-semibold">{deleteConfirm.name}</span>?
              {deleteConfirm.task_count > 0 && (
                <span className="block text-sm text-slate-muted mt-1">
                  {deleteConfirm.task_count} task(s) will be unassigned from this milestone.
                </span>
              )}
            </p>
            <div className="flex items-center justify-end gap-3">
              <Button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors"
              >
                Cancel
              </Button>
              <Button
                onClick={handleDelete}
                className="px-4 py-2 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MilestoneList;
