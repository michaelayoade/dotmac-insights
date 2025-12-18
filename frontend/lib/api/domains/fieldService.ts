/**
 * Field Service Domain API
 * Includes: Orders, Teams, Technicians, Schedule, Analytics
 */

import { fetchApi, fetchApiFormData } from '../core';

// =============================================================================
// TYPES
// =============================================================================

export type FieldServiceOrderStatus =
  | 'draft'
  | 'scheduled'
  | 'dispatched'
  | 'en_route'
  | 'on_site'
  | 'in_progress'
  | 'completed'
  | 'cancelled'
  | 'rescheduled'
  | 'failed';

export type FieldServiceOrderPriority =
  | 'emergency'
  | 'urgent'
  | 'high'
  | 'medium'
  | 'low';

export interface FieldServiceOrder {
  id: number;
  order_number: string;
  title: string;
  description?: string;
  status: FieldServiceOrderStatus;
  priority: FieldServiceOrderPriority;
  order_type?: string;
  customer_id?: number;
  customer_name?: string;
  address?: string;
  city?: string;
  state?: string;
  latitude?: number;
  longitude?: number;
  technician_id?: number;
  technician_name?: string;
  team_id?: number;
  scheduled_date?: string;
  scheduled_start_time?: string;
  scheduled_end_time?: string;
  actual_start_time?: string;
  actual_end_time?: string;
  estimated_duration_minutes?: number;
  checklist_template_id?: number;
  checklist?: FieldServiceChecklistItem[];
  photos?: FieldServicePhoto[];
  time_entries?: FieldServiceTimeEntry[];
  items?: FieldServiceItem[];
  notes?: string;
  created_at: string;
  updated_at?: string;
}

export interface FieldServiceOrderListResponse {
  data: FieldServiceOrder[];
  total: number;
  limit: number;
  offset: number;
}

export interface FieldServiceOrderCreatePayload {
  title: string;
  description?: string;
  priority?: FieldServiceOrderPriority;
  order_type?: string;
  customer_id?: number;
  address?: string;
  city?: string;
  state?: string;
  latitude?: number;
  longitude?: number;
  team_id?: number;
  scheduled_date?: string;
  scheduled_start_time?: string;
  scheduled_end_time?: string;
  estimated_duration_minutes?: number;
  checklist_template_id?: number;
  notes?: string;
}

export interface FieldServiceChecklistItem {
  id: number;
  order_id: number;
  item_text: string;
  is_required: boolean;
  is_completed: boolean;
  completed_at?: string;
  notes?: string;
  sort_order: number;
}

export interface FieldServiceChecklistTemplate {
  id: number;
  name: string;
  description?: string;
  items: { item_text: string; is_required: boolean; sort_order: number }[];
}

export interface FieldServicePhoto {
  id: number;
  order_id: number;
  photo_type: string;
  url: string;
  thumbnail_url?: string;
  caption?: string;
  uploaded_by?: number;
  created_at: string;
}

export interface FieldServiceTimeEntry {
  id: number;
  order_id: number;
  entry_type: string;
  start_time: string;
  end_time?: string;
  duration_minutes?: number;
  notes?: string;
}

export interface FieldServiceItem {
  id: number;
  order_id: number;
  item_name: string;
  item_code?: string;
  quantity: number;
  unit_price?: number;
  total_price?: number;
  is_billable: boolean;
}

export interface FieldServiceTeam {
  id: number;
  name: string;
  description?: string;
  manager_id?: number;
  is_active: boolean;
  technician_count?: number;
}

export interface FieldServiceTeamListResponse {
  data: FieldServiceTeam[];
  total: number;
}

export interface FieldServiceTechnician {
  id: number;
  user_id: number;
  name: string;
  email?: string;
  phone?: string;
  team_id?: number;
  team_name?: string;
  skills?: string[];
  is_available: boolean;
  current_location?: { latitude: number; longitude: number };
  active_order_id?: number;
  rating?: number;
  completed_orders_count?: number;
}

export interface FieldServiceTechnicianListResponse {
  data: FieldServiceTechnician[];
  total: number;
}

export interface FieldServiceDashboard {
  summary: {
    total_orders_today: number;
    completed_today: number;
    in_progress: number;
    overdue: number;
    avg_completion_time_minutes?: number;
    first_time_fix_rate?: number;
  };
  by_status: Record<FieldServiceOrderStatus, number>;
  by_type: Record<string, number>;
  by_priority: Record<FieldServiceOrderPriority, number>;
}

export interface FieldServiceCalendarEvent {
  id: number;
  order_id: number;
  order_number: string;
  title: string;
  customer_name?: string;
  technician_id?: number;
  technician_name?: string;
  team_id?: number;
  start: string;
  end: string;
  status: FieldServiceOrderStatus;
  priority: FieldServiceOrderPriority;
}

export interface FieldServiceDispatchBoardItem {
  technician: FieldServiceTechnician;
  orders: FieldServiceOrder[];
  availability: {
    is_available: boolean;
    next_available_at?: string;
  };
}

export interface FieldServiceAnalyticsDashboard {
  period: { start_date: string; end_date: string };
  total_orders: number;
  completed_orders: number;
  completion_rate: number;
  avg_response_time_minutes: number;
  avg_resolution_time_minutes: number;
  first_time_fix_rate: number;
  customer_satisfaction: number;
  revenue: number;
  by_order_type: { type: string; count: number; revenue: number }[];
  by_team: { team_id: number; team_name: string; count: number; completion_rate: number }[];
  trends: { date: string; orders: number; completed: number; revenue: number }[];
}

export interface FieldServiceTechnicianPerformance {
  technician_id: number;
  technician_name: string;
  team_name?: string;
  total_orders: number;
  completed_orders: number;
  avg_completion_time_minutes: number;
  first_time_fix_rate: number;
  customer_rating: number;
  utilization_rate: number;
  revenue_generated: number;
}

export interface FieldServiceOrderTypeBreakdown {
  type: string;
  count: number;
  percentage: number;
  avg_duration_minutes: number;
  completion_rate: number;
  revenue: number;
}

export interface FieldServiceDispatchPayload {
  technician_id: number;
  notes?: string;
  notify_customer?: boolean;
}

// =============================================================================
// FIELD SERVICE API
// =============================================================================

export const fieldServiceApi = {
  // -------------------------------------------------------------------------
  // Dashboard
  // -------------------------------------------------------------------------

  /** Get field service dashboard summary */
  getDashboard: () =>
    fetchApi<FieldServiceDashboard>('/field-service/dashboard'),

  // -------------------------------------------------------------------------
  // Orders
  // -------------------------------------------------------------------------

  /** List field service orders with optional filters */
  getOrders: (params?: {
    status?: FieldServiceOrderStatus;
    priority?: FieldServiceOrderPriority;
    team_id?: number;
    technician_id?: number;
    customer_id?: number;
    scheduled_date?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<FieldServiceOrderListResponse>('/field-service/orders', { params }),

  /** Get a specific order by ID */
  getOrder: (id: number | string) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}`),

  /** Create a new field service order */
  createOrder: (payload: FieldServiceOrderCreatePayload) =>
    fetchApi<FieldServiceOrder>('/field-service/orders', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** Update an existing order */
  updateOrder: (id: number | string, payload: Partial<FieldServiceOrderCreatePayload>) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  /** Delete an order */
  deleteOrder: (id: number | string) =>
    fetchApi<void>(`/field-service/orders/${id}`, { method: 'DELETE' }),

  // -------------------------------------------------------------------------
  // Order Status Actions
  // -------------------------------------------------------------------------

  /** Schedule a draft order */
  scheduleOrder: (id: number | string, payload?: { scheduled_date?: string; scheduled_start_time?: string }) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}/schedule`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),

  /** Dispatch an order to a technician */
  dispatchOrder: (id: number | string, payload: FieldServiceDispatchPayload) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}/dispatch`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** Mark technician as en route */
  startTravel: (id: number | string) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}/start-travel`, { method: 'POST' }),

  /** Mark technician as arrived on site */
  arriveOnSite: (id: number | string) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}/arrive`, { method: 'POST' }),

  /** Start work on the order */
  startWork: (id: number | string) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}/start-work`, { method: 'POST' }),

  /** Pause work on the order */
  pauseWork: (id: number | string, payload?: { reason?: string }) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}/pause`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),

  /** Resume work on the order */
  resumeWork: (id: number | string) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}/resume`, { method: 'POST' }),

  /** Complete the order */
  completeOrder: (id: number | string, payload?: { notes?: string; signature?: string }) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}/complete`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),

  /** Cancel the order */
  cancelOrder: (id: number | string, payload?: { reason?: string }) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),

  /** Reschedule the order */
  rescheduleOrder: (id: number | string, payload: { scheduled_date: string; scheduled_start_time?: string; reason?: string }) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}/reschedule`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** Generic status action (for dynamic actions) */
  updateOrderStatus: (id: number | string, action: string, payload?: Record<string, unknown>) =>
    fetchApi<FieldServiceOrder>(`/field-service/orders/${id}/${action}`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),

  // -------------------------------------------------------------------------
  // Order Photos
  // -------------------------------------------------------------------------

  /** Upload a photo for an order */
  uploadPhoto: (orderId: number | string, formData: FormData) =>
    fetchApiFormData<FieldServicePhoto>(`/field-service/orders/${orderId}/photos`, formData),

  /** Delete a photo from an order */
  deletePhoto: (orderId: number | string, photoId: number | string) =>
    fetchApi<void>(`/field-service/orders/${orderId}/photos/${photoId}`, { method: 'DELETE' }),

  // -------------------------------------------------------------------------
  // Teams
  // -------------------------------------------------------------------------

  /** List all teams */
  getTeams: () =>
    fetchApi<FieldServiceTeamListResponse>('/field-service/teams'),

  /** Get a specific team */
  getTeam: (id: number | string) =>
    fetchApi<FieldServiceTeam>(`/field-service/teams/${id}`),

  // -------------------------------------------------------------------------
  // Technicians
  // -------------------------------------------------------------------------

  /** List technicians with optional filters */
  getTechnicians: (params?: { team_id?: number; is_available?: boolean; limit?: number; offset?: number }) =>
    fetchApi<FieldServiceTechnicianListResponse>('/field-service/technicians', { params }),

  /** Get a specific technician */
  getTechnician: (id: number | string) =>
    fetchApi<FieldServiceTechnician>(`/field-service/technicians/${id}`),

  // -------------------------------------------------------------------------
  // Schedule
  // -------------------------------------------------------------------------

  /** Get calendar view of scheduled orders */
  getCalendar: (params?: { start_date?: string; end_date?: string; team_id?: number; technician_id?: number }) =>
    fetchApi<FieldServiceCalendarEvent[]>('/field-service/schedule/calendar', { params }),

  /** Get dispatch board view */
  getDispatchBoard: (params?: { date?: string; team_id?: number }) =>
    fetchApi<FieldServiceDispatchBoardItem[]>('/field-service/schedule/dispatch-board', { params }),

  // -------------------------------------------------------------------------
  // Checklist Templates
  // -------------------------------------------------------------------------

  /** List checklist templates */
  getChecklistTemplates: () =>
    fetchApi<{ data: FieldServiceChecklistTemplate[] }>('/field-service/checklist-templates'),

  /** Get a specific checklist template */
  getChecklistTemplate: (id: number | string) =>
    fetchApi<FieldServiceChecklistTemplate>(`/field-service/checklist-templates/${id}`),

  // -------------------------------------------------------------------------
  // Analytics
  // -------------------------------------------------------------------------

  /** Get analytics dashboard */
  getAnalyticsDashboard: (params?: { start_date?: string; end_date?: string; team_id?: number }) =>
    fetchApi<FieldServiceAnalyticsDashboard>('/field-service/analytics/dashboard', { params }),

  /** Get technician performance metrics */
  getTechnicianPerformance: (params?: { start_date?: string; end_date?: string; team_id?: number }) =>
    fetchApi<FieldServiceTechnicianPerformance[]>('/field-service/analytics/technician-performance', { params }),

  /** Get order type breakdown */
  getOrderTypeBreakdown: (params?: { start_date?: string; end_date?: string }) =>
    fetchApi<FieldServiceOrderTypeBreakdown[]>('/field-service/analytics/order-type-breakdown', { params }),
};

// =============================================================================
// STANDALONE EXPORTS (for backward compatibility)
// =============================================================================

export const getFieldServiceDashboard = fieldServiceApi.getDashboard;
export const getFieldServiceOrders = fieldServiceApi.getOrders;
export const getFieldServiceOrder = fieldServiceApi.getOrder;
export const createFieldServiceOrder = fieldServiceApi.createOrder;
export const updateFieldServiceOrder = fieldServiceApi.updateOrder;
export const deleteFieldServiceOrder = fieldServiceApi.deleteOrder;
export const scheduleFieldServiceOrder = fieldServiceApi.scheduleOrder;
export const dispatchFieldServiceOrder = fieldServiceApi.dispatchOrder;
export const startFieldServiceTravel = fieldServiceApi.startTravel;
export const arriveFieldServiceOnSite = fieldServiceApi.arriveOnSite;
export const startFieldServiceWork = fieldServiceApi.startWork;
export const pauseFieldServiceWork = fieldServiceApi.pauseWork;
export const resumeFieldServiceWork = fieldServiceApi.resumeWork;
export const completeFieldServiceOrder = fieldServiceApi.completeOrder;
export const cancelFieldServiceOrder = fieldServiceApi.cancelOrder;
export const rescheduleFieldServiceOrder = fieldServiceApi.rescheduleOrder;
export const updateFieldServiceOrderStatus = fieldServiceApi.updateOrderStatus;
export const uploadFieldServicePhoto = fieldServiceApi.uploadPhoto;
export const deleteFieldServicePhoto = fieldServiceApi.deletePhoto;
export const getFieldServiceTeams = fieldServiceApi.getTeams;
export const getFieldServiceTeam = fieldServiceApi.getTeam;
export const getFieldServiceTechnicians = fieldServiceApi.getTechnicians;
export const getFieldServiceTechnician = fieldServiceApi.getTechnician;
export const getFieldServiceCalendar = fieldServiceApi.getCalendar;
export const getFieldServiceDispatchBoard = fieldServiceApi.getDispatchBoard;
export const getFieldServiceChecklistTemplates = fieldServiceApi.getChecklistTemplates;
export const getFieldServiceChecklistTemplate = fieldServiceApi.getChecklistTemplate;
export const getFieldServiceAnalyticsDashboard = fieldServiceApi.getAnalyticsDashboard;
export const getFieldServiceTechnicianPerformance = fieldServiceApi.getTechnicianPerformance;
export const getFieldServiceOrderTypeBreakdown = fieldServiceApi.getOrderTypeBreakdown;
