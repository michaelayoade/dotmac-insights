/**
 * Consolidated Dashboard API
 *
 * Single-payload dashboard endpoints for improved performance.
 * Each endpoint returns all data needed for its respective dashboard page.
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

export interface SalesDashboardResponse {
  currency: string;
  generated_at: string;

  finance: {
    revenue: {
      mrr: number;
      arr: number;
      active_subscriptions: number;
    };
    collections: {
      last_30_days: number;
      invoiced_30_days: number;
      collection_rate: number;
    };
    outstanding: {
      total: number;
      overdue: number;
    };
    metrics: {
      dso: number;
    };
    invoices_by_status: Record<string, { count: number; total: number }>;
  };

  aging: {
    buckets: {
      current: { count: number; total: number };
      '1_30': { count: number; total: number };
      '31_60': { count: number; total: number };
      '61_90': { count: number; total: number };
      over_90: { count: number; total: number };
    };
  };

  revenue_trend: Array<{
    period: string;
    revenue: number;
    payment_count: number;
  }>;

  recent: {
    invoices: Array<{
      id: number;
      invoice_number: string | null;
      customer_name: string | null;
      total_amount: number;
      currency: string;
      status: string | null;
      invoice_date: string | null;
    }>;
    payments: Array<{
      id: number;
      receipt_number: string | null;
      customer_name: string | null;
      amount: number;
      currency: string;
      status: string | null;
      payment_date: string | null;
    }>;
    credit_notes: Array<{
      id: number;
      credit_number: string | null;
      customer_name: string | null;
      amount: number;
      currency: string;
      status: string | null;
      issue_date: string | null;
    }>;
    bills: Array<{
      id: number;
      supplier_name: string | null;
      grand_total: number;
      currency: string;
      status: string | null;
      posting_date: string | null;
    }>;
    purchase_payments: Array<{
      id: number;
      supplier: string | null;
      amount: number;
      posting_date: string | null;
    }>;
  };

  crm: {
    leads: {
      total: number;
      new: number;
      contacted: number;
      qualified: number;
      converted: number;
    };
    pipeline: {
      open_count: number;
      total_value: number;
      weighted_value: number;
      win_rate: number;
      won_count: number;
      lost_count: number;
    };
    stages: Array<{
      id: number;
      name: string;
      sequence: number;
      probability: number;
      is_won: boolean;
      is_lost: boolean;
      color: string | null;
      opportunity_count: number;
      opportunity_value: number;
    }>;
    upcoming_activities: Array<{
      id: number;
      activity_type: string | null;
      subject: string;
      scheduled_at: string | null;
      priority: string | null;
    }>;
    overdue_activities: Array<{
      id: number;
      activity_type: string | null;
      subject: string;
      scheduled_at: string | null;
      priority: string | null;
    }>;
  };
}

export interface PurchasingDashboardResponse {
  currency: string | null;
  generated_at: string;

  summary: {
    total_outstanding: number;
    total_overdue: number;
    overdue_percentage: number;
    supplier_count: number;
    total_bills: number;
    due_this_week: {
      count: number;
      total: number;
    };
    status_breakdown: Record<string, { count: number; total: number }>;
  };

  aging: {
    buckets: {
      current: { count: number; total: number };
      '1_30': { count: number; total: number };
      '31_60': { count: number; total: number };
      '61_90': { count: number; total: number };
      over_90: { count: number; total: number };
    };
  };

  top_suppliers: Array<{
    name: string;
    outstanding: number;
    bill_count: number;
  }>;

  recent: {
    bills: Array<{
      id: number;
      supplier_name: string | null;
      grand_total: number;
      outstanding_amount: number;
      currency: string;
      status: string | null;
      posting_date: string | null;
      due_date: string | null;
    }>;
    payments: Array<{
      id: number;
      supplier: string | null;
      amount: number;
      posting_date: string | null;
      voucher_no: string | null;
    }>;
    orders: Array<{
      order_no: string;
      supplier: string | null;
      date: string | null;
      total: number;
    }>;
    debit_notes: Array<{
      id: number;
      supplier: string | null;
      grand_total: number;
      posting_date: string | null;
      status: string | null;
    }>;
  };
}

export interface SupportDashboardResponse {
  generated_at: string;

  summary: {
    open_tickets: number;
    resolved_tickets: number;
    overdue_tickets: number;
    unassigned_tickets: number;
    avg_resolution_hours: number;
    sla_attainment: number;
    team_count: number;
    agent_count: number;
  };

  volume_trend: Array<{
    period: string;
    count: number;
  }>;

  sla_performance: Array<{
    period: string;
    total: number;
    met: number;
    breached: number;
    rate: number;
  }>;

  by_category: Array<{
    category: string;
    count: number;
  }>;

  queue_health: {
    unassigned_count: number;
    avg_wait_hours: number;
    total_agents: number;
    current_load: number;
  };

  sla_breaches: {
    total: number;
    by_priority: Record<string, number>;
  };
}

export interface FieldServiceDashboardResponse {
  generated_at: string;

  summary: {
    today_orders: number;
    completed_today: number;
    unassigned: number;
    overdue: number;
    week_completion_rate: number;
    avg_customer_rating: number;
  };

  by_status: Record<string, number>;
  by_type: Record<string, number>;

  today_schedule: Array<{
    id: number;
    order_number: string | null;
    order_type: string | null;
    status: string | null;
    customer_name: string | null;
    customer_address: string | null;
    scheduled_date: string | null;
    technician_name: string | null;
    priority: string | null;
  }>;
}

export interface FieldServiceScheduleDashboardResponse {
  generated_at: string;

  summary: {
    total_orders: number;
    unassigned: number;
    overdue: number;
    by_status: Record<string, number>;
  };

  teams: Array<{
    id: number;
    name: string;
    max_daily_orders: number;
    members: Array<{
      id: number;
      name: string;
      role: string;
      avatar_url: string | null;
    }>;
    member_count: number;
  }>;

  calendar_events: Array<{
    id: string;
    title: string;
    start: string;
    end: string;
    allDay: boolean;
    color: 'default' | 'success' | 'warning' | 'danger' | 'info';
    resourceId: string | null;
    metadata: {
      order_number: string | null;
      order_type: string | null;
      status: string | null;
      priority: string | null;
      customer_name: string | null;
      customer_address: string | null;
      technician_id: number | null;
      technician_name: string | null;
      team_id: number | null;
      city: string | null;
    };
  }>;

  dispatch_board: {
    date: string;
    resources: Array<{
      id: string;
      name: string;
      order_count: number;
      orders: Array<{
        id: number;
        order_number: string | null;
        status: string | null;
        priority: string | null;
        scheduled_time: string | null;
        customer_name: string | null;
        city: string | null;
      }>;
      completed: number;
      pending: number;
      availability: 'available' | 'busy' | 'scheduled' | 'done';
    }>;
  };
}

export interface AccountingDashboardResponse {
  currency: string;
  generated_at: string;
  fiscal_year: {
    start: string;
    end: string;
  };

  balance_sheet: {
    total_assets: number;
    total_liabilities: number;
    total_equity: number;
    net_worth: number;
  };

  income_statement: {
    total_income: number;
    total_expenses: number;
    net_income: number;
  };

  cash: {
    total: number;
    bank_accounts: Array<{
      id: number;
      account_name: string;
      bank_name: string | null;
      account_number: string;
      balance: number;
      currency: string;
    }>;
  };

  receivables: {
    total: number;
    top_customers: Array<{
      customer_name: string;
      outstanding: number;
      invoice_count: number;
    }>;
  };

  payables: {
    total: number;
    top_suppliers: Array<{
      supplier_name: string;
      outstanding: number;
      bill_count: number;
    }>;
  };

  ratios: {
    current_ratio: number;
    debt_to_equity: number;
    profit_margin: number;
  };

  counts: {
    suppliers: number;
    gl_entries: number;
  };

  fiscal_years: Array<{
    id: number;
    name: string;
    start_date: string | null;
    end_date: string | null;
    is_closed: boolean;
  }>;
}

// =============================================================================
// HR DASHBOARD
// =============================================================================

export interface HRDashboardResponse {
  generated_at: string;

  summary: {
    total_employees: number;
    active_employees: number;
    on_leave_today: number;
    present_today: number;
  };

  leave: {
    pending_approvals: number;
    by_status: Record<string, number>;
    trend: Array<{ month: string; count: number }>;
  };

  attendance: {
    status_30d: Record<string, number>;
    trend: Array<{ date: string; status_counts: Record<string, number> }>;
  };

  payroll_30d: {
    slip_count: number;
    gross_total: number;
    deduction_total: number;
    net_total: number;
  };

  recruitment: {
    open_positions: number;
    funnel: {
      applications: number;
      screened: number;
      interviewed: number;
      offered: number;
      hired: number;
    };
  };

  training: {
    scheduled_events: number;
    upcoming: Array<{
      id: number;
      event_name: string;
      start_time: string | null;
      type: string | null;
    }>;
  };

  onboarding: {
    active_count: number;
    recent: Array<{
      id: number;
      employee_name: string | null;
      status: string | null;
      date_of_joining: string | null;
    }>;
  };
}

export interface HRLeaveDashboardResponse {
  generated_at: string;

  summary: {
    pending_approvals: number;
    approved_in_range: number;
    on_leave_today: number;
  };

  calendar_events: Array<{
    id: string;
    title: string;
    start: string | null;
    end: string | null;
    allDay: boolean;
    color: 'warning' | 'info' | 'default';
    resourceId: string | null;
    metadata: {
      employee_id: number | null;
      employee_name: string | null;
      leave_type: string | null;
      status: string | null;
      total_days: number | null;
      reason: string | null;
      department: string | null;
    };
  }>;

  pending_requests: Array<{
    id: number;
    employee_id: number | null;
    employee_name: string | null;
    leave_type: string | null;
    from_date: string | null;
    to_date: string | null;
    total_days: number | null;
    reason: string | null;
    posting_date: string | null;
    department: string | null;
  }>;

  leave_by_type: Record<string, { count: number; total_days: number }>;

  leave_types: Array<{
    name: string;
    max_days_allowed: number | null;
    is_carry_forward: boolean;
  }>;
}

// =============================================================================
// INVENTORY DASHBOARD
// =============================================================================

export interface InventoryDashboardResponse {
  generated_at: string;

  summary: {
    total_value: number;
    total_items: number;
    total_warehouses: number;
    low_stock_alerts: number;
  };

  stock_by_warehouse: Array<{
    warehouse: string;
    value: number;
    items: number;
  }>;

  recent: {
    entries: Array<{
      id: number;
      stock_entry_type: string | null;
      posting_date: string | null;
      total_amount: number;
      from_warehouse: string | null;
      to_warehouse: string | null;
      docstatus: number;
    }>;
    items: Array<{
      id: number;
      item_code: string | null;
      item_name: string | null;
      stock_uom: string | null;
      total_stock_qty: number;
    }>;
  };

  counts: {
    total_entries: number;
  };
}

// =============================================================================
// ASSETS DASHBOARD
// =============================================================================

export interface AssetsDashboardResponse {
  generated_at: string;

  totals: {
    count: number;
    purchase_value: number;
    book_value: number;
    accumulated_depreciation: number;
  };

  by_status: Array<{ status: string; count: number }>;

  depreciation: {
    pending_count: number;
    pending_amount: number;
    entries: Array<{
      asset_id: number;
      asset_name: string | null;
      schedule_date: string | null;
      depreciation_amount: number;
    }>;
  };

  maintenance: {
    due_count: number;
    assets: Array<{
      id: number;
      asset_name: string;
      location: string | null;
      last_maintenance: string | null;
    }>;
  };

  expiring: {
    warranty: {
      count: number;
      assets: Array<{
        id: number;
        asset_name: string;
        warranty_expiry_date: string | null;
        days_remaining: number;
      }>;
    };
    insurance: {
      count: number;
      assets: Array<{
        id: number;
        asset_name: string;
        insurance_end_date: string | null;
        days_remaining: number;
      }>;
    };
  };
}

// =============================================================================
// EXPENSES DASHBOARD
// =============================================================================

export interface ExpensesDashboardResponse {
  generated_at: string;

  claims: {
    total: number;
    by_status: Record<string, { count: number; total: number }>;
    total_claimed_amount: number;
    recent: Array<{
      id: number;
      claim_number: string | null;
      title: string | null;
      total_claimed_amount: number;
      status: string | null;
      claim_date: string | null;
    }>;
  };

  advances: {
    total: number;
    by_status: Record<string, { count: number; outstanding: number }>;
    outstanding_amount: number;
    recent: Array<{
      id: number;
      advance_number: string | null;
      purpose: string | null;
      requested_amount: number;
      outstanding_amount: number;
      status: string | null;
      request_date: string | null;
    }>;
  };

  pending_approvals: number;
  trend: Array<{ month: string; claims: number; amount: number }>;
}

// =============================================================================
// PROJECTS DASHBOARD
// =============================================================================

export interface ProjectsDashboardResponse {
  generated_at: string;

  projects: {
    total: number;
    active: number;
    completed: number;
    on_hold: number;
    cancelled: number;
  };

  tasks: {
    total: number;
    open: number;
    overdue: number;
  };

  metrics: {
    avg_completion_percent: number;
    due_this_week: number;
  };

  financials: {
    total_billed: number;
    total_cost: number;
    total_margin: number;
  };

  recent: Array<{
    id: number;
    project_name: string;
    status: string | null;
    percent_complete: number;
    expected_end_date: string | null;
    department: string | null;
  }>;
}

// =============================================================================
// INBOX DASHBOARD
// =============================================================================

export interface InboxDashboardResponse {
  generated_at: string;

  summary: {
    open_count: number;
    pending_count: number;
    resolved_today: number;
    total_unread: number;
  };

  by_channel: Record<string, number>;
  by_priority: Record<string, number>;
  avg_response_time_hours: number;

  recent: Array<{
    id: number;
    subject: string | null;
    contact_name: string | null;
    contact_email: string | null;
    status: string | null;
    priority: string | null;
    unread_count: number;
    last_message_at: string | null;
  }>;
}

// =============================================================================
// CONTACTS DASHBOARD
// =============================================================================

export interface ContactsDashboardResponse {
  generated_at: string;

  summary: {
    total_contacts: number;
    new_30d: number;
    by_stage: Record<string, number>;
  };

  sources: Array<{ source: string; count: number }>;

  recent_activities: Array<{
    id: number;
    activity_type: string | null;
    subject: string;
    status: string | null;
    scheduled_at: string | null;
  }>;
}

// =============================================================================
// CUSTOMERS DASHBOARD
// =============================================================================

export interface CustomersDashboardResponse {
  generated_at: string;
  currency: string;

  summary: {
    total_customers: number;
    active: number;
    churned_30d: number;
  };

  billing: {
    outstanding: number;
    overdue: number;
    avg_invoice_value: number;
  };

  subscriptions: {
    active: number;
    mrr: number;
    by_plan: Array<{ plan: string; count: number }>;
  };

  recent: Array<{
    id: number;
    name: string | null;
    customer_name: string | null;
    territory: string | null;
    created_at: string | null;
  }>;
}

// =============================================================================
// CRM PIPELINE DASHBOARD
// =============================================================================

export interface CRMPipelineDashboardResponse {
  generated_at: string;
  currency: string;

  summary: {
    open_count: number;
    total_value: number;
    weighted_value: number;
    win_rate: number;
    won_count: number;
    lost_count: number;
  };

  stages: Array<{
    id: number;
    name: string;
    sequence: number;
    probability: number;
    is_won: boolean;
    is_lost: boolean;
    color: string | null;
    opportunity_count: number;
    opportunity_value: number;
  }>;

  kanban: {
    columns: Array<{
      id: string;
      title: string;
      color: string;
      count: number;
      value: number;
      cards: Array<{
        id: number;
        title: string;
        subtitle: string | null;
        value: number;
        currency: string;
        probability: number;
        expected_close_date: string | null;
        owner_name: string | null;
        owner_id: number | null;
        days_in_stage: number | null;
      }>;
    }>;
  };

  recent_activities: Array<{
    id: number;
    activity_type: string | null;
    subject: string;
    status: string | null;
    scheduled_at: string | null;
    priority: string | null;
    opportunity_id: number | null;
    opportunity_name: string | null;
  }>;
}

// =============================================================================
// LEADS DASHBOARD
// =============================================================================

export interface LeadsDashboardResponse {
  generated_at: string;

  summary: {
    total: number;
    new_30d: number;
    converted_30d: number;
    by_status: Record<string, number>;
  };

  sources: Array<{
    source: string;
    count: number;
  }>;

  leads: {
    items: Array<{
      id: number;
      lead_name: string;
      company_name: string | null;
      email_id: string | null;
      phone: string | null;
      source: string | null;
      status: string | null;
      lead_owner: string | null;
      territory: string | null;
      industry: string | null;
      city: string | null;
      state: string | null;
      converted: boolean;
      created_at: string | null;
      updated_at: string | null;
    }>;
    total: number;
    limit: number;
    offset: number;
  };

  recent_conversions: Array<{
    id: number;
    lead_name: string;
    company_name: string | null;
    source: string | null;
    converted_at: string | null;
    customer_id: number | null;
  }>;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

export const dashboardsApi = {
  /**
   * Get consolidated Sales Dashboard data (13 calls → 1)
   */
  getSalesDashboard: (currency?: string) =>
    fetchApi<SalesDashboardResponse>('/dashboards/sales', {
      params: currency ? { currency } : undefined,
    }),

  /**
   * Get consolidated Purchasing Dashboard data (8 calls → 1)
   */
  getPurchasingDashboard: (currency?: string, params?: { start_date?: string; end_date?: string }) =>
    fetchApi<PurchasingDashboardResponse>('/dashboards/purchasing', {
      params: {
        ...(currency ? { currency } : {}),
        ...(params?.start_date ? { start_date: params.start_date } : {}),
        ...(params?.end_date ? { end_date: params.end_date } : {}),
      },
    }),

  /**
   * Get consolidated Support Dashboard data (7 calls → 1)
   */
  getSupportDashboard: (params?: { start_date?: string; end_date?: string }) =>
    fetchApi<SupportDashboardResponse>('/dashboards/support', {
      params: {
        ...(params?.start_date ? { start_date: params.start_date } : {}),
        ...(params?.end_date ? { end_date: params.end_date } : {}),
      },
    }),

  /**
   * Get consolidated Field Service Dashboard data (2 calls → 1)
   */
  getFieldServiceDashboard: () =>
    fetchApi<FieldServiceDashboardResponse>('/dashboards/field-service'),

  /**
   * Get consolidated Field Service Schedule data (3 calls → 1)
   * For calendar and dispatch board views
   */
  getFieldServiceScheduleDashboard: (params: {
    start_date: string;
    end_date: string;
    team_id?: number;
    technician_id?: number;
  }) =>
    fetchApi<FieldServiceScheduleDashboardResponse>('/dashboards/field-service-schedule', {
      params: {
        start_date: params.start_date,
        end_date: params.end_date,
        ...(params.team_id ? { team_id: params.team_id } : {}),
        ...(params.technician_id ? { technician_id: params.technician_id } : {}),
      },
    }),

  /**
   * Get consolidated Accounting Dashboard data (11 calls → 1)
   */
  getAccountingDashboard: (currency?: string) =>
    fetchApi<AccountingDashboardResponse>('/dashboards/accounting', {
      params: currency ? { currency } : undefined,
    }),

  /**
   * Get consolidated HR Dashboard data (11 calls → 1)
   */
  getHRDashboard: () =>
    fetchApi<HRDashboardResponse>('/dashboards/hr'),

  /**
   * Get consolidated Inventory Dashboard data (3 calls → 1)
   */
  getInventoryDashboard: () =>
    fetchApi<InventoryDashboardResponse>('/dashboards/inventory'),

  /**
   * Get consolidated Assets Dashboard data (5 calls → 1)
   */
  getAssetsDashboard: (daysAhead?: number) =>
    fetchApi<AssetsDashboardResponse>('/dashboards/assets', {
      params: daysAhead ? { days_ahead: daysAhead } : undefined,
    }),

  /**
   * Get consolidated Expenses Dashboard data (2 calls → 1)
   */
  getExpensesDashboard: () =>
    fetchApi<ExpensesDashboardResponse>('/dashboards/expenses'),

  /**
   * Get consolidated Projects Dashboard data (2 calls → 1)
   */
  getProjectsDashboard: () =>
    fetchApi<ProjectsDashboardResponse>('/dashboards/projects'),

  /**
   * Get consolidated Inbox Dashboard data (3 calls → 1)
   */
  getInboxDashboard: () =>
    fetchApi<InboxDashboardResponse>('/dashboards/inbox'),

  /**
   * Get consolidated Contacts Dashboard data
   */
  getContactsDashboard: () =>
    fetchApi<ContactsDashboardResponse>('/dashboards/contacts'),

  /**
   * Get consolidated Customers Dashboard data
   */
  getCustomersDashboard: (currency?: string) =>
    fetchApi<CustomersDashboardResponse>('/dashboards/customers', {
      params: currency ? { currency } : undefined,
    }),

  /**
   * Get consolidated HR Leave Dashboard data (3 calls → 1)
   * For leave calendar and pending approvals views
   */
  getHRLeaveDashboard: (params: {
    start_date: string;
    end_date: string;
    department_id?: number;
  }) =>
    fetchApi<HRLeaveDashboardResponse>('/dashboards/hr-leave', {
      params: {
        start_date: params.start_date,
        end_date: params.end_date,
        ...(params.department_id ? { department_id: params.department_id } : {}),
      },
    }),

  /**
   * Get consolidated CRM Pipeline Dashboard data (3 calls → 1)
   * For kanban board and pipeline views
   */
  getCRMPipelineDashboard: (currency?: string) =>
    fetchApi<CRMPipelineDashboardResponse>('/dashboards/crm-pipeline', {
      params: currency ? { currency } : undefined,
    }),

  /**
   * Get consolidated Leads Dashboard data (3 calls → 1)
   * For leads list and sources views
   */
  getLeadsDashboard: (params?: {
    status?: string;
    source?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<LeadsDashboardResponse>('/dashboards/leads', {
      params: params ? {
        ...(params.status ? { status: params.status } : {}),
        ...(params.source ? { source: params.source } : {}),
        ...(params.limit ? { limit: params.limit } : {}),
        ...(params.offset ? { offset: params.offset } : {}),
      } : undefined,
    }),
};
