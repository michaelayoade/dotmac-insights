/**
 * Workflow Tasks API domain
 * Unified task management across all modules
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

export interface WorkflowTask {
  id: number;
  source_type: string;
  source_id: number;
  title: string;
  description?: string;
  action_url?: string;
  assignee_user_id?: number;
  assignee_employee_id?: number;
  assignee_team_id?: number;
  assignee_display_name?: string;
  assigned_at: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  due_at?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled' | 'expired';
  completed_at?: string;
  module: string;
  company?: string;
  metadata?: Record<string, any>;
  is_overdue: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkflowTaskListResponse {
  items: WorkflowTask[];
  total: number;
  limit: number;
  offset: number;
}

export interface WorkflowTaskSummary {
  pending: number;
  overdue: number;
  due_today: number;
  completed_today: number;
  by_module: Record<string, number>;
  by_priority: Record<string, number>;
}

export interface ScheduledTask {
  id: number;
  celery_task_id: string;
  task_name: string;
  scheduled_for: string;
  executed_at?: string;
  status: 'scheduled' | 'executed' | 'cancelled' | 'failed';
  source_type?: string;
  source_id?: number;
  payload?: Record<string, any>;
  result?: Record<string, any>;
  error?: string;
  created_at: string;
}

export interface ScheduleReminderPayload {
  entity_type: string;
  entity_id: number;
  remind_at: string;
  message: string;
  title?: string;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

export const workflowTasksApi = {
  /**
   * Get unified task list for current user
   */
  getMyTasks: (params?: {
    status?: string;
    module?: string;
    priority?: string;
    overdue_only?: boolean;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<WorkflowTaskListResponse>('/v1/workflow-tasks/my-tasks', { params }),

  /**
   * Get task summary for current user
   */
  getMyTasksSummary: () =>
    fetchApi<WorkflowTaskSummary>('/v1/workflow-tasks/my-tasks/summary'),

  /**
   * Get a specific task
   */
  getTask: (taskId: number) =>
    fetchApi<WorkflowTask>(`/v1/workflow-tasks/${taskId}`),

  /**
   * Mark a task as completed
   */
  completeTask: (taskId: number) =>
    fetchApi<WorkflowTask>(`/v1/workflow-tasks/${taskId}/complete`, {
      method: 'POST',
    }),

  /**
   * Snooze a task
   */
  snoozeTask: (taskId: number, snoozeUntil: string) =>
    fetchApi<WorkflowTask>(`/v1/workflow-tasks/${taskId}/snooze`, {
      method: 'POST',
      body: { snooze_until: snoozeUntil },
    }),

  /**
   * Update task status
   */
  updateTaskStatus: (taskId: number, status: string) =>
    fetchApi<WorkflowTask>(`/v1/workflow-tasks/${taskId}/status`, {
      method: 'PATCH',
      body: { status },
    }),

  /**
   * Schedule a reminder
   */
  scheduleReminder: (payload: ScheduleReminderPayload) =>
    fetchApi<ScheduledTask>('/v1/workflow-tasks/schedule-reminder', {
      method: 'POST',
      body: payload,
    }),

  /**
   * List scheduled tasks
   */
  getScheduledTasks: (params?: {
    status?: string;
    source_type?: string;
    source_id?: number;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<ScheduledTask[]>('/v1/workflow-tasks/scheduled', { params }),

  /**
   * Cancel a scheduled task
   */
  cancelScheduledTask: (scheduledTaskId: number, reason?: string) =>
    fetchApi<{ status: string; scheduled_task_id: number }>(
      `/v1/workflow-tasks/scheduled/${scheduledTaskId}`,
      {
        method: 'DELETE',
        params: reason ? { reason } : undefined,
      }
    ),
};
