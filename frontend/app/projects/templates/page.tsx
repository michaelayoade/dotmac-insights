'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  FileText,
  Plus,
  Clock,
  CheckCircle,
  XCircle,
  CalendarDays,
  ClipboardList,
  Milestone,
  MoreVertical,
  Pencil,
  Trash2,
  Copy,
} from 'lucide-react';
import { useProjectTemplates, useTemplateMutations } from '@/hooks/useApi';
import { mutate } from 'swr';
import type { ProjectTemplate } from '@/lib/api/domains/projects';

const priorityColors: Record<string, string> = {
  low: 'text-slate-400',
  medium: 'text-amber-400',
  high: 'text-rose-400',
};

function TemplateCard({ template, onDelete }: { template: ProjectTemplate; onDelete: (id: number) => void }) {
  const [showMenu, setShowMenu] = useState(false);
  const router = useRouter();

  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-5 hover:border-amber-400/30 transition-all group">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <Link
            href={`/projects/templates/${template.id}`}
            className="text-slate-100 font-medium hover:text-amber-400 transition-colors line-clamp-1"
          >
            {template.name}
          </Link>
          {template.project_type && (
            <span className="text-xs text-slate-500 ml-2">{template.project_type}</span>
          )}
        </div>
        <div className="relative">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="p-1 rounded hover:bg-slate-700/50 text-slate-400 hover:text-slate-300"
          >
            <MoreVertical className="w-4 h-4" />
          </button>
          {showMenu && (
            <div
              className="absolute right-0 top-8 w-40 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-10"
              onMouseLeave={() => setShowMenu(false)}
            >
              <Link
                href={`/projects/templates/${template.id}`}
                className="flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:bg-slate-700/50 hover:text-slate-100"
              >
                <Pencil className="w-3.5 h-3.5" /> Edit
              </Link>
              <button
                onClick={() => {
                  setShowMenu(false);
                  router.push(`/projects/templates/new?duplicate=${template.id}`);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:bg-slate-700/50 hover:text-slate-100"
              >
                <Copy className="w-3.5 h-3.5" /> Duplicate
              </button>
              <button
                onClick={() => {
                  setShowMenu(false);
                  onDelete(template.id);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-rose-400 hover:bg-rose-500/10"
              >
                <Trash2 className="w-3.5 h-3.5" /> Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {template.description && (
        <p className="text-sm text-slate-400 mb-4 line-clamp-2">{template.description}</p>
      )}

      <div className="flex items-center gap-4 text-xs text-slate-500 mb-4">
        <span className="flex items-center gap-1">
          <ClipboardList className="w-3.5 h-3.5" />
          {template.task_count ?? 0} tasks
        </span>
        <span className="flex items-center gap-1">
          <Milestone className="w-3.5 h-3.5" />
          {template.milestone_count ?? 0} milestones
        </span>
        {template.estimated_duration_days && (
          <span className="flex items-center gap-1">
            <CalendarDays className="w-3.5 h-3.5" />
            {template.estimated_duration_days} days
          </span>
        )}
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1 text-xs ${template.is_active ? 'text-emerald-400' : 'text-slate-500'}`}>
            {template.is_active ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
            {template.is_active ? 'Active' : 'Inactive'}
          </span>
          <span className={`text-xs ${priorityColors[template.default_priority] || 'text-slate-400'}`}>
            {template.default_priority} priority
          </span>
        </div>
        <Link
          href={`/projects/new?template=${template.id}`}
          className="text-xs text-amber-400 hover:text-amber-300 font-medium"
        >
          Use Template
        </Link>
      </div>
    </div>
  );
}

export default function ProjectTemplatesPage() {
  const [filter, setFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const { data, isLoading, error } = useProjectTemplates(
    filter === 'all' ? undefined : { is_active: filter === 'active' }
  );
  const mutations = useTemplateMutations();
  const [deleting, setDeleting] = useState<number | null>(null);

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this template?')) return;
    setDeleting(id);
    try {
      await mutations.delete(id);
      mutate(['project-templates', filter === 'all' ? undefined : { is_active: filter === 'active' }]);
    } catch (err) {
      console.error('Failed to delete template:', err);
      alert('Failed to delete template');
    } finally {
      setDeleting(null);
    }
  };

  const templates: ProjectTemplate[] = data?.data || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Project Templates</h1>
          <p className="text-slate-400 text-sm mt-1">
            Create reusable project structures with predefined tasks and milestones
          </p>
        </div>
        <Link
          href="/projects/templates/new"
          className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 text-slate-900 font-medium rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Template
        </Link>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-700/50 pb-3">
        {(['all', 'active', 'inactive'] as const).map((status) => (
          <button
            key={status}
            onClick={() => setFilter(status)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              filter === status
                ? 'bg-amber-500/20 text-amber-400'
                : 'text-slate-400 hover:text-slate-300 hover:bg-slate-800/50'
            }`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-400" />
        </div>
      ) : error ? (
        <div className="text-center py-20">
          <p className="text-rose-400">Failed to load templates</p>
        </div>
      ) : templates.length === 0 ? (
        <div className="text-center py-20 bg-slate-800/30 rounded-lg border border-slate-700/50">
          <FileText className="w-12 h-12 mx-auto text-slate-600 mb-4" />
          <h3 className="text-lg font-medium text-slate-300 mb-2">No templates found</h3>
          <p className="text-slate-500 mb-6">
            {filter === 'all'
              ? 'Create your first project template to get started.'
              : `No ${filter} templates found.`
            }
          </p>
          <Link
            href="/projects/templates/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 text-slate-900 font-medium rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create Template
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((template: ProjectTemplate) => (
            <TemplateCard key={template.id} template={template} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
