/**
 * Insights Domain API (Deep Insights, Data Quality, Anomalies)
 * Includes: Data Completeness, Customer Segments/Health, Relationship Map, Financial/Operational Insights
 */

import { fetchApi } from '../core';

// =============================================================================
// DATA COMPLETENESS
// =============================================================================

export interface FieldCompleteness {
  field: string;
  filled: number;
  total: number;
  percent: number;
  sample_values?: string[];
}

export interface EntityCompleteness {
  total: number;
  fields: FieldCompleteness[];
  overall_score: number;
}

export interface DataCompletenessResponse {
  entities: Record<string, EntityCompleteness>;
  recommendations: string[];
  priority_fields: string[];
}

// =============================================================================
// CUSTOMER SEGMENTS (Deep Insights)
// =============================================================================

export interface InsightsCustomerSegment {
  segment: string;
  count: number;
  percentage: number;
  avg_mrr?: number;
  total_mrr?: number;
}

export interface InsightsCustomerSegmentsResponse {
  by_status: InsightsCustomerSegment[];
  by_type: InsightsCustomerSegment[];
  by_billing_type: InsightsCustomerSegment[];
  by_tenure: InsightsCustomerSegment[];
  by_mrr_tier: InsightsCustomerSegment[];
  by_geography: InsightsCustomerSegment[];
  by_pop: InsightsCustomerSegment[];
  total_customers: number;
}

// =============================================================================
// CUSTOMER HEALTH (Deep Insights)
// =============================================================================

export interface InsightsCustomerHealthRecord {
  customer_id: number;
  customer_name: string;
  email: string | null;
  status: string;
  health_score: number;
  risk_level: string;
  payment_health: {
    days_since_last_payment: number | null;
    outstanding_amount: number;
    overdue_invoices: number;
    payment_regularity: string;
  };
  support_health: {
    open_tickets: number;
    recent_conversations: number;
    avg_resolution_time: number | null;
  };
  engagement: {
    tenure_days: number;
    subscription_count: number;
    mrr: number;
  };
  risk_factors: string[];
  opportunities: string[];
}

export interface InsightsCustomerHealthResponse {
  customers: InsightsCustomerHealthRecord[];
  summary: {
    total_analyzed: number;
    health_distribution: Record<string, number>;
    at_risk_count: number;
    avg_health_score: number;
  };
  recommendations: string[];
}

// =============================================================================
// RELATIONSHIP MAP
// =============================================================================

export interface EntityRelationship {
  entity: string;
  total: number;
  linked: number;
  orphaned: number;
  link_rate: number;
}

export interface RelationshipMapResponse {
  entities: EntityRelationship[];
  data_quality: {
    overall_linkage_rate: number;
    strong_links: string[];
    weak_links: string[];
    missing_links: string[];
  };
  recommendations: string[];
}

// =============================================================================
// FINANCIAL INSIGHTS
// =============================================================================

export interface FinancialInsightsResponse {
  revenue: {
    total_mrr: number;
    total_invoiced: number;
    total_paid: number;
    total_outstanding: number;
    collection_rate: number;
    by_currency: Record<string, number>;
  };
  aging: {
    current: number;
    past_30: number;
    past_60: number;
    past_90: number;
    over_90: number;
  };
  payment_methods: Record<string, { count: number; amount: number }>;
  trends: {
    avg_payment_delay: number;
    avg_invoice_amount: number;
  };
  recommendations: string[];
}

// =============================================================================
// OPERATIONAL INSIGHTS
// =============================================================================

export interface OperationalInsightsResponse {
  support: {
    total_tickets: number;
    open_tickets: number;
    avg_resolution_hours: number;
    resolution_rate: number;
    by_priority: Record<string, number>;
    by_type: Record<string, number>;
  };
  conversations: {
    total: number;
    open: number;
    resolved: number;
    by_channel: Record<string, number>;
  };
  employees: {
    total: number;
    by_department: Record<string, number>;
    avg_tickets_per_agent: number;
  };
  recommendations: string[];
}

// =============================================================================
// ANOMALIES
// =============================================================================

export interface Anomaly {
  type: string;
  severity: string;
  entity: string;
  description: string;
  affected_count: number;
  sample_ids?: number[];
}

export interface AnomaliesResponse {
  anomalies: Anomaly[];
  summary: {
    total_issues: number;
    critical: number;
    warning: number;
    info: number;
  };
  recommendations: string[];
}

// =============================================================================
// DATA AVAILABILITY
// =============================================================================

export interface DataAvailabilityEntity {
  entity: string;
  total: number;
  fields: string[];
  date_range?: {
    earliest: string | null;
    latest: string | null;
  };
}

export interface DataAvailabilityGap {
  entity: string;
  issue: string;
  recommendation: string;
}

export interface DataAvailabilityResponse {
  available: DataAvailabilityEntity[];
  gaps: DataAvailabilityGap[];
  summary: {
    total_entities: number;
    total_records: number;
    well_populated: number;
    needs_attention: number;
  };
}

// =============================================================================
// CHURN RISK
// =============================================================================

export interface ChurnRiskCustomer {
  id: number;
  name: string;
  email: string | null;
  account_number: string | null;
  risk_score: number;
  risk_factors: string[];
  last_payment_date: string | null;
  days_since_payment: number;
  outstanding_amount: number;
  open_tickets: number;
}

export interface ChurnRiskSummary {
  overdue_customers: number;
  recent_cancellations_30d: number;
  suspended_customers: number;
  high_ticket_customers: number;
}

export interface ChurnRiskResponse {
  summary: ChurnRiskSummary;
  customers?: ChurnRiskCustomer[];
}

// =============================================================================
// API OBJECT
// =============================================================================

export const insightsApi = {
  // Data Completeness
  getDataCompleteness: () =>
    fetchApi<DataCompletenessResponse>('/insights/data-completeness'),

  // Customer Segments (Deep)
  getCustomerSegments: () =>
    fetchApi<InsightsCustomerSegmentsResponse>('/insights/customer-segments'),

  // Customer Health (Deep)
  getCustomerHealth: (limit = 100, riskLevel?: string) =>
    fetchApi<InsightsCustomerHealthResponse>('/insights/customer-health', {
      params: { limit, risk_level: riskLevel },
    }),

  // Relationship Map
  getRelationshipMap: () =>
    fetchApi<RelationshipMapResponse>('/insights/relationship-map'),

  // Financial Insights
  getFinancialInsights: () =>
    fetchApi<FinancialInsightsResponse>('/insights/financial-insights'),

  // Operational Insights
  getOperationalInsights: () =>
    fetchApi<OperationalInsightsResponse>('/insights/operational-insights'),

  // Anomalies
  getAnomalies: () =>
    fetchApi<AnomaliesResponse>('/insights/anomalies'),

  // Data Availability
  getDataAvailability: () =>
    fetchApi<DataAvailabilityResponse>('/insights/data-availability'),

  // Churn Risk
  getChurnRisk: (limit = 20) =>
    fetchApi<ChurnRiskResponse>('/insights/churn-risk', { params: { limit } }),
};
