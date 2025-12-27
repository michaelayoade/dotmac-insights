'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Save,
  Plus,
  Trash2,
  GripVertical,
  ClipboardList,
  Milestone,
} from 'lucide-react';
import { useProjectTemplate, useTemplateMutations } from '@/hooks/useApi';
import { mutate } from 'swr';
import type {
  ProjectTemplateCreatePayload,
  MilestoneTemplatePayload,
  TaskTemplatePayload,
  ProjectPriority,
  MilestoneTemplateItem,
  TaskTemplateItem,
} from '@/lib/api/domains/projects';

const priorities: { value: ProjectPriority; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
];

interface MilestoneFormItem extends MilestoneTemplatePayload {
  _tempId: string;
}

interface TaskFormItem extends TaskTemplatePayload {
  _tempId: string;
  _milestoneTempId?: string;
}

export default function NewTemplatePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const duplicateId = searchParams.get('duplicate');

  const { data: sourceTemplate } = useProjectTemplate(duplicateId ? parseInt(duplicateId) : null);
  const mutations = useTemplateMutations();

  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<'general' | 'milestones' | 'tasks'>('general');

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [projectType, setProjectType] = useState('');
  const [defaultPriority, setDefaultPriority] = useState<ProjectPriority>('medium');
  const [estimatedDays, setEstimatedDays] = useState<number | ''>('');
  const [defaultNotes, setDefaultNotes] = useState('');
  const [isActive, setIsActive] = useState(true);

  const [milestones, setMilestones] = useState<MilestoneFormItem[]>([]);
  const [tasks, setTasks] = useState<TaskFormItem[]>([]);

  // Load source template for duplication
  useEffect(() => {
    if (sourceTemplate) {
      setName(`${sourceTemplate.name} (Copy)`);
      setDescription(sourceTemplate.description || '');
      setProjectType(sourceTemplate.project_type || '');
      setDefaultPriority(sourceTemplate.default_priority);
      setEstimatedDays(sourceTemplate.estimated_duration_days || '');
      setDefaultNotes(sourceTemplate.default_notes || '');
      setIsActive(sourceTemplate.is_active);

      if (sourceTemplate.milestone_templates) {
        setMilestones(
          sourceTemplate.milestone_templates.map((m: MilestoneTemplateItem, idx: number) => ({
            _tempId: `m-${idx}`,
            name: m.name,
            description: m.description,
            start_day_offset: m.start_day_offset,
            end_day_offset: m.end_day_offset,
            idx: m.idx,
          }))
        );
      }

      if (sourceTemplate.task_templates) {
        setTasks(
          sourceTemplate.task_templates.map((t: TaskTemplateItem, idx: number) => ({
            _tempId: `t-${idx}`,
            subject: t.subject,
            description: t.description,
            priority: t.priority,
            start_day_offset: t.start_day_offset,
            duration_days: t.duration_days,
            default_assigned_role: t.default_assigned_role,
            is_group: t.is_group,
            idx: t.idx,
          }))
        );
      }
    }
  }, [sourceTemplate]);

  const addMilestone = () => {
    setMilestones([
      ...milestones,
      {
        _tempId: `m-${Date.now()}`,
        name: '',
        description: null,
        start_day_offset: 0,
        end_day_offset: 7,
        idx: milestones.length,
      },
    ]);
  };

  const removeMilestone = (tempId: string) => {
    setMilestones(milestones.filter((m) => m._tempId !== tempId));
  };

  const updateMilestone = (tempId: string, updates: Partial<MilestoneFormItem>) => {
    setMilestones(milestones.map((m) => (m._tempId === tempId ? { ...m, ...updates } : m)));
  };

  const addTask = () => {
    setTasks([
      ...tasks,
      {
        _tempId: `t-${Date.now()}`,
        subject: '',
        description: null,
        priority: 'medium',
        start_day_offset: 0,
        duration_days: 1,
        default_assigned_role: null,
        is_group: false,
        idx: tasks.length,
      },
    ]);
  };

  const removeTask = (tempId: string) => {
    setTasks(tasks.filter((t) => t._tempId !== tempId));
  };

  const updateTask = (tempId: string, updates: Partial<TaskFormItem>) => {
    setTasks(tasks.map((t) => (t._tempId === tempId ? { ...t, ...updates } : t)));
  };

  const handleSave = async () => {
    if (!name.trim()) {
      alert('Template name is required');
      return;
    }

    setSaving(true);
    try {
      const payload: ProjectTemplateCreatePayload = {
        name: name.trim(),
        description: description.trim() || null,
        project_type: projectType.trim() || null,
        default_priority: defaultPriority,
        estimated_duration_days: estimatedDays || null,
        default_notes: defaultNotes.trim() || null,
        is_active: isActive,
        milestone_templates: milestones
          .filter((m) => m.name.trim())
          .map(({ _tempId, ...m }) => ({
            ...m,
            name: m.name.trim(),
          })),
        task_templates: tasks
          .filter((t) => t.subject.trim())
          .map(({ _tempId, _milestoneTempId, ...t }) => ({
            ...t,
            subject: t.subject.trim(),
          })),
      };

      await mutations.create(payload);
      mutate((key) => Array.isArray(key) && key[0] === 'project-templates');
      router.push('/projects/templates');
    } catch (err) {
      console.error('Failed to create template:', err);
      alert('Failed to create template');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/projects/templates"
            className="p-2 rounded-lg hover:bg-slate-800/50 text-slate-400 hover:text-slate-300 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-100">
              {duplicateId ? 'Duplicate Template' : 'New Template'}
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Create a reusable project structure
            </p>
          </div>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-900 font-medium rounded-lg transition-colors"
        >
          <Save className="w-4 h-4" />
          {saving ? 'Saving...' : 'Save Template'}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-slate-700/50">
        {(['general', 'milestones', 'tasks'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-amber-400 text-amber-400'
                : 'border-transparent text-slate-400 hover:text-slate-300'
            }`}
          >
            {tab === 'general' && 'General'}
            {tab === 'milestones' && (
              <span className="flex items-center gap-1.5">
                <Milestone className="w-4 h-4" />
                Milestones ({milestones.length})
              </span>
            )}
            {tab === 'tasks' && (
              <span className="flex items-center gap-1.5">
                <ClipboardList className="w-4 h-4" />
                Tasks ({tasks.length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* General Tab */}
      {activeTab === 'general' && (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-6 space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Template Name <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Website Redesign"
                className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Project Type
              </label>
              <input
                type="text"
                value={projectType}
                onChange={(e) => setProjectType(e.target.value)}
                placeholder="e.g., Internal, Client"
                className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500/50"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Describe what this template is for..."
              className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500/50 resize-none"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Default Priority
              </label>
              <select
                value={defaultPriority}
                onChange={(e) => setDefaultPriority(e.target.value as ProjectPriority)}
                className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-amber-500/50"
              >
                {priorities.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Estimated Duration (days)
              </label>
              <input
                type="number"
                value={estimatedDays}
                onChange={(e) => setEstimatedDays(e.target.value ? parseInt(e.target.value) : '')}
                min={1}
                placeholder="e.g., 30"
                className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500/50"
              />
            </div>
            <div className="flex items-center">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-amber-500 focus:ring-amber-500/20"
                />
                <span className="text-sm text-slate-300">Active template</span>
              </label>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">
              Default Notes
            </label>
            <textarea
              value={defaultNotes}
              onChange={(e) => setDefaultNotes(e.target.value)}
              rows={3}
              placeholder="Notes to include in projects created from this template..."
              className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500/50 resize-none"
            />
          </div>
        </div>
      )}

      {/* Milestones Tab */}
      {activeTab === 'milestones' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">
              Define milestones with day offsets from project start date
            </p>
            <button
              onClick={addMilestone}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" /> Add Milestone
            </button>
          </div>

          {milestones.length === 0 ? (
            <div className="text-center py-12 bg-slate-800/30 rounded-lg border border-slate-700/50">
              <Milestone className="w-10 h-10 mx-auto text-slate-600 mb-3" />
              <p className="text-slate-400">No milestones added yet</p>
              <button
                onClick={addMilestone}
                className="mt-4 text-amber-400 hover:text-amber-300 text-sm font-medium"
              >
                Add your first milestone
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {milestones.map((milestone, index) => (
                <div
                  key={milestone._tempId}
                  className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4"
                >
                  <div className="flex items-start gap-3">
                    <div className="pt-2 text-slate-600 cursor-move">
                      <GripVertical className="w-4 h-4" />
                    </div>
                    <div className="flex-1 grid grid-cols-1 md:grid-cols-4 gap-3">
                      <div className="md:col-span-2">
                        <input
                          type="text"
                          value={milestone.name}
                          onChange={(e) =>
                            updateMilestone(milestone._tempId, { name: e.target.value })
                          }
                          placeholder="Milestone name"
                          className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500/50 text-sm"
                        />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-500 whitespace-nowrap">Start day</span>
                          <input
                            type="number"
                            value={milestone.start_day_offset}
                            onChange={(e) =>
                              updateMilestone(milestone._tempId, {
                                start_day_offset: parseInt(e.target.value) || 0,
                              })
                            }
                            min={0}
                            className="w-full px-2 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-amber-500/50 text-sm"
                          />
                        </div>
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-500 whitespace-nowrap">End day</span>
                          <input
                            type="number"
                            value={milestone.end_day_offset}
                            onChange={(e) =>
                              updateMilestone(milestone._tempId, {
                                end_day_offset: parseInt(e.target.value) || 0,
                              })
                            }
                            min={0}
                            className="w-full px-2 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-amber-500/50 text-sm"
                          />
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => removeMilestone(milestone._tempId)}
                      className="p-1.5 text-slate-500 hover:text-rose-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tasks Tab */}
      {activeTab === 'tasks' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">
              Define tasks with day offsets and durations
            </p>
            <button
              onClick={addTask}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" /> Add Task
            </button>
          </div>

          {tasks.length === 0 ? (
            <div className="text-center py-12 bg-slate-800/30 rounded-lg border border-slate-700/50">
              <ClipboardList className="w-10 h-10 mx-auto text-slate-600 mb-3" />
              <p className="text-slate-400">No tasks added yet</p>
              <button
                onClick={addTask}
                className="mt-4 text-amber-400 hover:text-amber-300 text-sm font-medium"
              >
                Add your first task
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {tasks.map((task) => (
                <div
                  key={task._tempId}
                  className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4"
                >
                  <div className="flex items-start gap-3">
                    <div className="pt-2 text-slate-600 cursor-move">
                      <GripVertical className="w-4 h-4" />
                    </div>
                    <div className="flex-1 grid grid-cols-1 md:grid-cols-5 gap-3">
                      <div className="md:col-span-2">
                        <input
                          type="text"
                          value={task.subject}
                          onChange={(e) => updateTask(task._tempId, { subject: e.target.value })}
                          placeholder="Task subject"
                          className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500/50 text-sm"
                        />
                      </div>
                      <div>
                        <select
                          value={task.priority}
                          onChange={(e) =>
                            updateTask(task._tempId, { priority: e.target.value as ProjectPriority })
                          }
                          className="w-full px-2 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-amber-500/50 text-sm"
                        >
                          {priorities.map((p) => (
                            <option key={p.value} value={p.value}>
                              {p.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-slate-500">Day</span>
                          <input
                            type="number"
                            value={task.start_day_offset}
                            onChange={(e) =>
                              updateTask(task._tempId, {
                                start_day_offset: parseInt(e.target.value) || 0,
                              })
                            }
                            min={0}
                            className="w-full px-2 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-amber-500/50 text-sm"
                          />
                        </div>
                      </div>
                      <div>
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-slate-500">Dur</span>
                          <input
                            type="number"
                            value={task.duration_days}
                            onChange={(e) =>
                              updateTask(task._tempId, {
                                duration_days: parseInt(e.target.value) || 1,
                              })
                            }
                            min={1}
                            className="w-full px-2 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-amber-500/50 text-sm"
                          />
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => removeTask(task._tempId)}
                      className="p-1.5 text-slate-500 hover:text-rose-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
