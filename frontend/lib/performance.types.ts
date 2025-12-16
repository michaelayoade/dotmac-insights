/**
 * Performance Module Types
 *
 * TypeScript interfaces for KPI/KRA definitions, scorecards, and analytics.
 */

// ============= ENUMS =============

export type PeriodType = 'monthly' | 'quarterly' | 'semi_annual' | 'annual' | 'custom';
export type PeriodStatus = 'draft' | 'active' | 'scoring' | 'review' | 'finalized' | 'archived';
export type DataSource = 'manual' | 'ticketing' | 'field_service' | 'finance' | 'crm' | 'attendance' | 'project';
export type Aggregation = 'sum' | 'avg' | 'count' | 'min' | 'max' | 'percent' | 'ratio';
export type ScoringMethod = 'linear' | 'threshold' | 'band' | 'binary';
export type ScorecardStatus = 'pending' | 'computing' | 'computed' | 'in_review' | 'approved' | 'disputed' | 'finalized';
export type OverrideReason = 'data_correction' | 'extenuating_circumstances' | 'partial_period' | 'system_error' | 'managerial_discretion' | 'other';

// ============= PERIODS =============

export interface EvaluationPeriod {
  id: number;
  code: string;
  name: string;
  period_type: PeriodType;
  status: PeriodStatus;
  start_date: string;
  end_date: string;
  scoring_deadline: string | null;
  review_deadline: string | null;
  created_at: string;
  updated_at: string;
  scorecard_count: number;
  computed_count: number;
  finalized_count: number;
}

export interface PeriodCreateInput {
  code: string;
  name: string;
  period_type: PeriodType;
  start_date: string;
  end_date: string;
  scoring_deadline?: string;
  review_deadline?: string;
}

export interface PeriodUpdateInput {
  name?: string;
  scoring_deadline?: string;
  review_deadline?: string;
}

export interface PeriodListResponse {
  items: EvaluationPeriod[];
  total: number;
}

// ============= KPI DEFINITIONS =============

export interface KPIDefinition {
  id: number;
  code: string;
  name: string;
  description: string | null;
  data_source: DataSource;
  aggregation: Aggregation;
  query_config: Record<string, unknown> | null;
  scoring_method: ScoringMethod;
  min_value: number | null;
  target_value: number | null;
  max_value: number | null;
  threshold_config: Record<string, unknown> | null;
  higher_is_better: boolean;
  created_at: string;
  updated_at: string;
  kra_count: number;
}

export interface KPICreateInput {
  code: string;
  name: string;
  description?: string;
  data_source: DataSource;
  aggregation: Aggregation;
  query_config?: Record<string, unknown>;
  scoring_method: ScoringMethod;
  min_value?: number;
  target_value?: number;
  max_value?: number;
  threshold_config?: Record<string, unknown>;
  higher_is_better?: boolean;
}

export interface KPIUpdateInput {
  name?: string;
  description?: string;
  query_config?: Record<string, unknown>;
  scoring_method?: ScoringMethod;
  min_value?: number;
  target_value?: number;
  max_value?: number;
  threshold_config?: Record<string, unknown>;
  higher_is_better?: boolean;
}

export interface KPIBinding {
  id: number;
  kpi_id: number;
  employee_id: number | null;
  department_id: number | null;
  designation_id: number | null;
  target_override: number | null;
  effective_from: string | null;
  effective_to: string | null;
  created_at: string;
}

export interface KPIListResponse {
  items: KPIDefinition[];
  total: number;
}

// ============= KRA DEFINITIONS =============

export interface KPILink {
  id: number;
  kpi_id: number;
  kpi_code: string;
  kpi_name: string;
  weightage: number;
  idx: number;
}

export interface KRADefinition {
  id: number;
  code: string;
  name: string;
  description: string | null;
  category: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  kpi_count: number;
  kpis: KPILink[];
}

export interface KRACreateInput {
  code: string;
  name: string;
  description?: string;
  category?: string;
}

export interface KRAUpdateInput {
  name?: string;
  description?: string;
  category?: string;
  is_active?: boolean;
}

export interface KRAListResponse {
  items: KRADefinition[];
  total: number;
}

// ============= TEMPLATES =============

export interface TemplateItem {
  id: number;
  kra_id: number;
  kra_code: string;
  kra_name: string;
  weightage: number;
  idx: number;
}

export interface ScorecardTemplate {
  id: number;
  code: string;
  name: string;
  applicable_departments: string[] | null;
  applicable_designations: string[] | null;
  version: number;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  items: TemplateItem[];
  total_weightage: number;
}

export interface TemplateItemInput {
  kra_id: number;
  weightage: number;
  idx: number;
}

export interface TemplateCreateInput {
  code: string;
  name: string;
  applicable_departments?: string[];
  applicable_designations?: string[];
  is_default?: boolean;
  items?: TemplateItemInput[];
}

export interface TemplateUpdateInput {
  name?: string;
  applicable_departments?: string[];
  applicable_designations?: string[];
  is_default?: boolean;
  is_active?: boolean;
}

export interface TemplateListResponse {
  items: ScorecardTemplate[];
  total: number;
}

// ============= SCORECARDS =============

export interface KPIResult {
  id: number;
  kpi_id: number;
  kpi_code: string;
  kpi_name: string;
  kra_id: number | null;
  raw_value: number | null;
  target_value: number | null;
  computed_score: number | null;
  final_score: number | null;
  weightage_in_kra: number | null;
  weighted_score: number | null;
  evidence_links: string[] | null;
}

export interface KRAResult {
  id: number;
  kra_id: number;
  kra_code: string;
  kra_name: string;
  computed_score: number | null;
  final_score: number | null;
  weightage_in_scorecard: number | null;
  weighted_score: number | null;
  kpi_results: KPIResult[];
}

export interface Scorecard {
  id: number;
  employee_id: number;
  employee_name: string | null;
  employee_code: string | null;
  department: string | null;
  designation: string | null;
  evaluation_period_id: number;
  period_code: string;
  period_name: string;
  template_id: number;
  template_name: string;
  status: ScorecardStatus;
  total_weighted_score: number | null;
  final_rating: string | null;
  reviewed_by_id: number | null;
  reviewed_at: string | null;
  finalized_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScorecardDetail extends Scorecard {
  kra_results: KRAResult[];
}

export interface ScorecardListResponse {
  items: Scorecard[];
  total: number;
}

export interface GenerateScorecardInput {
  employee_ids?: number[];
  template_id?: number;
}

// ============= REVIEWS =============

export interface ScoreOverride {
  id: number;
  scorecard_instance_id: number;
  override_type: 'kpi' | 'kra' | 'overall';
  kpi_result_id: number | null;
  kra_result_id: number | null;
  original_score: number | null;
  overridden_score: number | null;
  reason: OverrideReason;
  justification: string | null;
  overridden_by_id: number | null;
  created_at: string;
}

export interface OverrideInput {
  override_type: 'kpi' | 'kra' | 'overall';
  kpi_result_id?: number;
  kra_result_id?: number;
  new_score: number;
  reason: OverrideReason;
  justification?: string;
}

export interface ReviewNote {
  id: number;
  scorecard_instance_id: number;
  note_type: string | null;
  content: string;
  kpi_result_id: number | null;
  kra_result_id: number | null;
  is_private: boolean;
  created_by_id: number | null;
  created_at: string;
}

export interface ReviewNoteInput {
  content: string;
  note_type?: string;
  kpi_result_id?: number;
  kra_result_id?: number;
  is_private?: boolean;
}

export interface ReviewQueueItem {
  scorecard_id: number;
  employee_id: number;
  employee_name: string;
  department: string | null;
  designation: string | null;
  period_name: string;
  status: ScorecardStatus;
  total_score: number | null;
  submitted_at: string | null;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
  pending_count: number;
  in_review_count: number;
}

// ============= ANALYTICS =============

export interface DashboardSummary {
  active_period: {
    id: number;
    code: string;
    name: string;
    status: PeriodStatus;
  } | null;
  total_employees: number;
  scorecards_generated: number;
  scorecards_computed: number;
  scorecards_in_review: number;
  scorecards_finalized: number;
  avg_score: number | null;
  score_distribution: {
    outstanding: number;
    exceeds: number;
    meets: number;
    below: number;
  };
  top_performers: Array<{
    employee_id: number;
    employee_name: string;
    department: string | null;
    score: number | null;
  }>;
  improvement_needed: Array<{
    employee_id: number;
    employee_name: string;
    department: string | null;
    score: number | null;
  }>;
}

export interface TeamPerformance {
  department: string;
  employee_count: number;
  avg_score: number | null;
  min_score: number | null;
  max_score: number | null;
  finalized_count: number;
}

export interface ScoreTrend {
  period_code: string;
  period_name: string;
  avg_score: number | null;
  employee_count: number;
}

export interface ScoreDistribution {
  rating: string;
  min_score: number;
  max_score: number;
  count: number;
  percentage: number;
}

export interface BonusEligibility {
  employee_id: number;
  employee_name: string;
  department: string | null;
  final_score: number | null;
  rating: string | null;
  bonus_factor: number | null;
  bonus_band: string | null;
}

export interface KRABreakdown {
  kra_id?: number;
  kra_code?: string;
  kra_name: string;
  avg_score: number | null;
  employee_count?: number;
  count?: number;
}

// Analytics
export interface PerformanceTrendPoint {
  period_id?: number;
  period_code?: string;
  period_name: string;
  avg_score: number;
  employee_count?: number;
  department?: string | null;
}

export interface ScoreDistributionSummary {
  outstanding?: number;
  exceeds?: number;
  meets?: number;
  below?: number;
}
