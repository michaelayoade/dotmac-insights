/**
 * Projects Domain API
 * Includes: Projects, Tasks, Dashboard, Analytics
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

export type ProjectStatus = 'open' | 'completed' | 'cancelled' | 'on_hold';
export type ProjectPriority = 'low' | 'medium' | 'high';

export interface ProjectUser {
  user?: string | null;
  full_name?: string | null;
  email?: string | null;
  project_status?: string | null;
  view_attachments?: boolean;
  welcome_email_sent?: boolean;
  idx?: number;
}

export interface ProjectListItem {
  id: number;
  erpnext_id: string | null;
  project_name: string;
  project_type: string | null;
  status: ProjectStatus;
  priority: ProjectPriority | null;
  department: string | null;
  customer_id: number | null;
  percent_complete: number | null;
  expected_start_date: string | null;
  expected_end_date: string | null;
  estimated_costing: number | null;
  total_billed_amount: number | null;
  is_overdue: boolean;
  task_count: number | null;
  created_at: string | null;
  write_back_status?: string | null;
}

export interface ProjectListResponse {
  total: number;
  limit: number;
  offset: number;
  data: ProjectListItem[];
}

export interface ProjectDetail extends ProjectListItem {
  company?: string | null;
  cost_center?: string | null;
  project_manager_id?: number | null;
  project_manager?: string | null;
  erpnext_customer?: string | null;
  erpnext_sales_order?: string | null;
  percent_complete_method?: string | null;
  is_active?: string | null;
  actual_time?: number | null;
  total_consumed_material_cost?: number | null;
  total_costing_amount?: number | null;
  total_expense_claim?: number | null;
  total_purchase_cost?: number | null;
  total_sales_amount?: number | null;
  total_billable_amount?: number | null;
  gross_margin?: number | null;
  per_gross_margin?: number | null;
  collect_progress?: boolean;
  frequency?: string | null;
  message?: string | null;
  notes?: string | null;
  actual_start_date?: string | null;
  actual_end_date?: string | null;
  from_time?: string | null;
  to_time?: string | null;
  customer?: Record<string, unknown> | null;
  users?: ProjectUser[];
  tasks?: unknown[];
  task_stats?: Record<string, unknown>;
  expenses?: unknown[];
  time_tracking?: Record<string, unknown>;
}

export interface ProjectPayload {
  project_name?: string;
  project_type?: string | null;
  status?: ProjectStatus;
  priority?: ProjectPriority;
  department?: string | null;
  company?: string | null;
  cost_center?: string | null;
  customer_id?: number | null;
  project_manager_id?: number | null;
  erpnext_customer?: string | null;
  erpnext_sales_order?: string | null;
  percent_complete?: number | null;
  percent_complete_method?: string | null;
  is_active?: string | null;
  actual_time?: number | null;
  total_consumed_material_cost?: number | null;
  estimated_costing?: number | null;
  total_costing_amount?: number | null;
  total_expense_claim?: number | null;
  total_purchase_cost?: number | null;
  total_sales_amount?: number | null;
  total_billable_amount?: number | null;
  total_billed_amount?: number | null;
  gross_margin?: number | null;
  per_gross_margin?: number | null;
  collect_progress?: boolean;
  frequency?: string | null;
  message?: string | null;
  notes?: string | null;
  expected_start_date?: string | null;
  expected_end_date?: string | null;
  actual_start_date?: string | null;
  actual_end_date?: string | null;
  from_time?: string | null;
  to_time?: string | null;
  users?: ProjectUser[];
}

export interface ProjectsDashboard {
  cards?: Record<string, number>;
  projects?: {
    total?: number;
    active?: number;
    completed?: number;
    on_hold?: number;
    cancelled?: number;
  };
  tasks?: {
    total?: number;
    open?: number;
    overdue?: number;
  };
  financials?: {
    total_billed?: number;
  };
  metrics?: {
    avg_completion_percent?: number;
    due_this_week?: number;
    [key: string]: unknown;
  };
  by_priority?: Record<string, number>;
}

export interface ProjectTaskListResponse {
  total: number;
  limit: number;
  offset: number;
  data: unknown[];
}

export interface ProjectListParams {
  status?: string;
  priority?: ProjectPriority;
  customer_id?: number;
  project_type?: string;
  department?: string;
  search?: string;
  overdue_only?: boolean;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export interface ProjectTaskParams {
  project_id?: number;
  status?: string;
  priority?: string;
  assigned_to?: string;
  task_type?: string;
  search?: string;
  overdue_only?: boolean;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

// =============================================================================
// API
// =============================================================================

export const projectsApi = {
  // =========================================================================
  // PROJECTS
  // =========================================================================

  getProjects: (params?: ProjectListParams) =>
    fetchApi<ProjectListResponse>('/projects', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  getProjectDetail: (id: number) => fetchApi<ProjectDetail>(`/projects/${id}`),

  createProject: (body: ProjectPayload & { project_name: string }) =>
    fetchApi<ProjectDetail>('/projects', { method: 'POST', body: JSON.stringify(body) }),

  updateProject: (id: number, body: ProjectPayload) =>
    fetchApi<ProjectDetail>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteProject: (id: number) =>
    fetchApi<{ message: string; id: number }>(`/projects/${id}`, { method: 'DELETE' }),

  // =========================================================================
  // DASHBOARD & ANALYTICS
  // =========================================================================

  getProjectsDashboard: () => fetchApi<ProjectsDashboard>('/projects/dashboard'),

  getProjectsStatusTrend: (months = 12) =>
    fetchApi<unknown>('/projects/analytics/status-trend', { params: { months } }),

  getProjectsTaskDistribution: () =>
    fetchApi<unknown>('/projects/analytics/task-distribution'),

  getProjectsPerformance: () => fetchApi<unknown>('/projects/analytics/project-performance'),

  getProjectsDepartmentSummary: (months = 12) =>
    fetchApi<unknown>('/projects/analytics/department-summary', { params: { months } }),

  // =========================================================================
  // TASKS
  // =========================================================================

  getProjectTasks: (params?: ProjectTaskParams) =>
    fetchApi<ProjectTaskListResponse>('/projects/tasks', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  getTaskDetail: (id: number) => fetchApi<unknown>(`/projects/tasks/${id}`),
};

export default projectsApi;
