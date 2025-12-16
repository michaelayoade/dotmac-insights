/**
 * Performance Module API Hooks
 *
 * SWR hooks for fetching and mutating performance data.
 */
import useSWR from 'swr';
import useSWRMutation from 'swr/mutation';
import { buildApiUrl, fetcher, apiFetch, buildQueryString } from '@/lib/api';
import type {
  EvaluationPeriod,
  PeriodCreateInput,
  PeriodUpdateInput,
  PeriodListResponse,
  PeriodType,
  PeriodStatus,
  KPIDefinition,
  KPICreateInput,
  KPIUpdateInput,
  KPIListResponse,
  KPIBinding,
  DataSource,
  KRADefinition,
  KRACreateInput,
  KRAUpdateInput,
  KRAListResponse,
  KPILink,
  ScorecardTemplate,
  TemplateCreateInput,
  TemplateUpdateInput,
  TemplateListResponse,
  TemplateItemInput,
  Scorecard,
  ScorecardDetail,
  ScorecardListResponse,
  GenerateScorecardInput,
  ScorecardStatus,
  ReviewQueueResponse,
  ScoreOverride,
  OverrideInput,
  ReviewNote,
  ReviewNoteInput,
  DashboardSummary,
  TeamPerformance,
  ScoreTrend,
  PerformanceTrendPoint,
  ScoreDistributionSummary,
  BonusEligibility,
  KRABreakdown,
} from '@/lib/performance.types';

const BASE_URL = '/performance';

// ============= PERIODS =============

interface UsePeriodListParams {
  status?: PeriodStatus;
  period_type?: PeriodType;
  year?: number;
  limit?: number;
  offset?: number;
}

export function usePeriodList(params: UsePeriodListParams = {}) {
  const query = buildQueryString(params as Record<string, string | number | boolean | null | undefined>);
  return useSWR<PeriodListResponse>(
    [`${BASE_URL}/periods`, params],
    () => fetcher(`${BASE_URL}/periods${query}`)
  );
}

export function usePeriod(id: number | null) {
  return useSWR<EvaluationPeriod>(
    id ? [`${BASE_URL}/periods`, id] : null,
    () => fetcher(`${BASE_URL}/periods/${id}`)
  );
}

export function useCreatePeriod() {
  return useSWRMutation<EvaluationPeriod, Error, string, PeriodCreateInput>(
    `${BASE_URL}/periods`,
    async (url, { arg }) => {
      return apiFetch(url, { method: 'POST', body: JSON.stringify(arg) });
    }
  );
}

export function useUpdatePeriod(id: number) {
  return useSWRMutation<EvaluationPeriod, Error, string, PeriodUpdateInput>(
    `${BASE_URL}/periods/${id}`,
    async (url, { arg }) => {
      return apiFetch(url, { method: 'PATCH', body: JSON.stringify(arg) });
    }
  );
}

export function useActivatePeriod(id: number) {
  return useSWRMutation<{ success: boolean }, Error, string>(
    `${BASE_URL}/periods/${id}/activate`,
    async (url: string) => {
      return apiFetch<{ success: boolean }>(url, { method: 'POST' });
    }
  );
}

export function useStartScoring(id: number) {
  return useSWRMutation<{ success: boolean }, Error>(
    `${BASE_URL}/periods/${id}/start-scoring`,
    async (url: string) => {
      return apiFetch<{ success: boolean }>(url, { method: 'POST' });
    }
  );
}

export function useFinalizePeriod(id: number) {
  return useSWRMutation<{ success: boolean }, Error>(
    `${BASE_URL}/periods/${id}/finalize`,
    async (url: string) => {
      return apiFetch<{ success: boolean }>(url, { method: 'POST' });
    }
  );
}

// ============= KPIs =============

interface UseKPIListParams {
  search?: string;
  data_source?: DataSource;
  limit?: number;
  offset?: number;
}

export function useKPIList(params: UseKPIListParams = {}) {
  const query = buildQueryString(params as Record<string, string | number | boolean | null | undefined>);
  return useSWR<KPIListResponse>(
    [`${BASE_URL}/kpis`, params],
    () => fetcher(`${BASE_URL}/kpis${query}`)
  );
}

export function useKPI(id: number | null) {
  return useSWR<KPIDefinition>(
    id ? [`${BASE_URL}/kpis`, id] : null,
    () => fetcher(`${BASE_URL}/kpis/${id}`)
  );
}

export function useCreateKPI() {
  return useSWRMutation<KPIDefinition, Error, string, KPICreateInput>(
    `${BASE_URL}/kpis`,
    async (url, { arg }) => {
      return apiFetch(url, { method: 'POST', body: JSON.stringify(arg) });
    }
  );
}

export function useUpdateKPI(id: number) {
  return useSWRMutation<KPIDefinition, Error, string, KPIUpdateInput>(
    `${BASE_URL}/kpis/${id}`,
    async (url, { arg }) => {
      return apiFetch(url, { method: 'PATCH', body: JSON.stringify(arg) });
    }
  );
}

export function useKPIBindings(kpiId: number | null) {
  return useSWR<KPIBinding[]>(
    kpiId ? [`${BASE_URL}/kpis`, kpiId, 'bindings'] : null,
    () => fetcher(`${BASE_URL}/kpis/${kpiId}/bindings`)
  );
}

// ============= KRAs =============

interface UseKRAListParams {
  search?: string;
  category?: string;
  active_only?: boolean;
  limit?: number;
  offset?: number;
}

export function useKRAList(params: UseKRAListParams = {}) {
  const query = buildQueryString(params as Record<string, string | number | boolean | null | undefined>);
  return useSWR<KRAListResponse>(
    [`${BASE_URL}/kras`, params],
    () => fetcher(`${BASE_URL}/kras${query}`)
  );
}

export function useKRA(id: number | null) {
  return useSWR<KRADefinition>(
    id ? [`${BASE_URL}/kras`, id] : null,
    () => fetcher(`${BASE_URL}/kras/${id}`)
  );
}

export function useKRACategories() {
  return useSWR<{ categories: string[] }>(
    `${BASE_URL}/kras/categories`,
    async () => fetcher(`${BASE_URL}/kras/categories`) as Promise<{ categories: string[] }>
  );
}

export function useCreateKRA() {
  return useSWRMutation<KRADefinition, Error, string, KRACreateInput>(
    `${BASE_URL}/kras`,
    async (url, { arg }) => {
      return apiFetch(url, { method: 'POST', body: JSON.stringify(arg) });
    }
  );
}

export function useUpdateKRA(id: number) {
  return useSWRMutation<KRADefinition, Error, string, KRAUpdateInput>(
    `${BASE_URL}/kras/${id}`,
    async (url, { arg }) => {
      return apiFetch(url, { method: 'PATCH', body: JSON.stringify(arg) });
    }
  );
}

export function useReplaceKRAKPIs(kraId: number) {
  return useSWRMutation<KPILink[], Error, string, Array<{ kpi_id: number; weightage: number; idx: number }>>(
    `${BASE_URL}/kras/${kraId}/kpis`,
    async (url, { arg }) => {
      return apiFetch(url, { method: 'PUT', body: JSON.stringify(arg) });
    }
  );
}

// ============= TEMPLATES =============

interface UseTemplateListParams {
  active_only?: boolean;
  department?: string;
  designation?: string;
  limit?: number;
  offset?: number;
}

export function useTemplateList(params: UseTemplateListParams = {}) {
  const query = buildQueryString(params as Record<string, string | number | boolean | null | undefined>);
  return useSWR<TemplateListResponse>(
    [`${BASE_URL}/templates`, params],
    () => fetcher(`${BASE_URL}/templates${query}`)
  );
}

export function useTemplate(id: number | null) {
  return useSWR<ScorecardTemplate>(
    id ? [`${BASE_URL}/templates`, id] : null,
    () => fetcher(`${BASE_URL}/templates/${id}`)
  );
}

export function useCreateTemplate() {
  return useSWRMutation<ScorecardTemplate, Error, string, TemplateCreateInput>(
    `${BASE_URL}/templates`,
    async (url, { arg }) => {
      return apiFetch(url, { method: 'POST', body: JSON.stringify(arg) });
    }
  );
}

export function useUpdateTemplate(id: number) {
  return useSWRMutation<ScorecardTemplate, Error, string, TemplateUpdateInput>(
    `${BASE_URL}/templates/${id}`,
    async (url, { arg }) => {
      return apiFetch(url, { method: 'PATCH', body: JSON.stringify(arg) });
    }
  );
}

export function useReplaceTemplateItems(templateId: number) {
  return useSWRMutation<ScorecardTemplate, Error, string, TemplateItemInput[]>(
    `${BASE_URL}/templates/${templateId}/items`,
    async (url, { arg }) => {
      return apiFetch(url, { method: 'PUT', body: JSON.stringify(arg) });
    }
  );
}

export function useCloneTemplate(id: number) {
  return useSWRMutation<ScorecardTemplate, Error, string, { new_code: string; new_name: string }>(
    `${BASE_URL}/templates/${id}/clone`,
    async (url, { arg }) => {
      const query = buildQueryString(arg);
      return apiFetch(`${url}${query}`, { method: 'POST' });
    }
  );
}

// ============= SCORECARDS =============

interface UseScorecardListParams {
  period_id?: number;
  employee_id?: number;
  department?: string;
  status?: ScorecardStatus;
  limit?: number;
  offset?: number;
}

export function useScorecardList(params: UseScorecardListParams = {}) {
  const query = buildQueryString(params as Record<string, string | number | boolean | null | undefined>);
  return useSWR<ScorecardListResponse>(
    [`${BASE_URL}/scorecards`, params],
    () => fetcher(`${BASE_URL}/scorecards${query}`)
  );
}

export function useScorecard(id: number | null) {
  return useSWR<ScorecardDetail>(
    id ? [`${BASE_URL}/scorecards`, id] : null,
    () => fetcher(`${BASE_URL}/scorecards/${id}`)
  );
}

export function useGenerateScorecards(periodId: number) {
  return useSWRMutation<
    { success: boolean; created: number; skipped: number },
    Error,
    string,
    GenerateScorecardInput
  >(
    `${BASE_URL}/scorecards/generate?period_id=${periodId}`,
    async (url, { arg }) => {
      return apiFetch(url, { method: 'POST', body: JSON.stringify(arg) });
    }
  );
}

export function useComputeScorecard(id: number) {
  return useSWRMutation<{ success: boolean }, Error>(
    `${BASE_URL}/scorecards/${id}/compute`,
    async (url: string, _options: Readonly<{ arg: never }>) => {
      return apiFetch<{ success: boolean }>(url, { method: 'POST' });
    }
  );
}

export function useSubmitScorecard(id: number) {
  return useSWRMutation<{ success: boolean }, Error>(
    `${BASE_URL}/scorecards/${id}/submit`,
    async (url: string): Promise<{ success: boolean }> => {
      return apiFetch(url, { method: 'POST' }) as Promise<{ success: boolean }>;
    }
  );
}

// ============= REVIEWS =============

interface UseReviewQueueParams {
  period_id?: number;
  department?: string;
  limit?: number;
  offset?: number;
}

export function useReviewQueue(params: UseReviewQueueParams = {}) {
  const query = buildQueryString(params as Record<string, string | number | boolean | null | undefined>);
  return useSWR<ReviewQueueResponse>(
    [`${BASE_URL}/reviews/queue`, params],
    () => fetcher(`${BASE_URL}/reviews/queue${query}`)
  );
}

export function useApproveScorecard(id: number) {
  return useSWRMutation<{ success: boolean }, Error>(
    `${BASE_URL}/reviews/scorecards/${id}/approve`,
    async (url: string, _options: Readonly<{ arg: never }>): Promise<{ success: boolean }> => {
      return apiFetch(url, { method: 'POST' }) as Promise<{ success: boolean }>;
    }
  );
}

export function useRejectScorecard(id: number) {
  return useSWRMutation<{ success: boolean }, Error, string, { reason: string }>(
    `${BASE_URL}/reviews/scorecards/${id}/reject`,
    async (url: string, { arg }) => {
      return apiFetch(url, { method: 'POST', body: JSON.stringify(arg) });
    }
  );
}

export function useCreateOverride(scorecardId: number) {
  return useSWRMutation<ScoreOverride, Error, string, OverrideInput>(
    `${BASE_URL}/reviews/scorecards/${scorecardId}/override`,
    async (url: string, { arg }) => {
      return apiFetch(url, { method: 'POST', body: JSON.stringify(arg) });
    }
  );
}

export function useScorecardOverrides(scorecardId: number | null) {
  return useSWR<ScoreOverride[]>(
    scorecardId ? [`${BASE_URL}/reviews/scorecards`, scorecardId, 'overrides'] : null,
    () => fetcher(`${BASE_URL}/reviews/scorecards/${scorecardId}/overrides`)
  );
}

export function useScorecardNotes(scorecardId: number | null, includePrivate = false) {
  const query = buildQueryString({ include_private: includePrivate });
  return useSWR<ReviewNote[]>(
    scorecardId ? [`${BASE_URL}/reviews/scorecards`, scorecardId, 'notes', includePrivate] : null,
    () => fetcher(`${BASE_URL}/reviews/scorecards/${scorecardId}/notes${query}`)
  );
}

export function useCreateNote(scorecardId: number) {
  return useSWRMutation<ReviewNote, Error, string, ReviewNoteInput>(
    `${BASE_URL}/reviews/scorecards/${scorecardId}/notes`,
    async (url: string, { arg }) => {
      return apiFetch(url, { method: 'POST', body: JSON.stringify(arg) });
    }
  );
}

export function useFinalizeScorecard(id: number) {
  return useSWRMutation<{ success: boolean }, Error>(
    `${BASE_URL}/reviews/scorecards/${id}/finalize`,
    async (url: string, _options: Readonly<{ arg: never }>): Promise<{ success: boolean }> => {
      return apiFetch(url, { method: 'POST' }) as Promise<{ success: boolean }>;
    }
  );
}

// ============= ANALYTICS =============

export function usePerformanceDashboard(periodId?: number) {
  const query = periodId ? buildQueryString({ period_id: periodId }) : '';
  return useSWR<DashboardSummary>(
    [`${BASE_URL}/analytics/dashboard`, periodId],
    () => fetcher(`${BASE_URL}/analytics/dashboard${query}`)
  );
}

export function useTeamPerformance(periodId: number) {
  return useSWR<TeamPerformance[]>(
    [`${BASE_URL}/analytics/team`, periodId],
    () => fetcher(`${BASE_URL}/analytics/team?period_id=${periodId}`)
  );
}

export function useScoreTrends(params: { employee_id?: number; department?: string; limit?: number } = {}) {
  const query = buildQueryString(params);
  return useSWR<ScoreTrend[]>(
    [`${BASE_URL}/analytics/trends`, params],
    () => fetcher(`${BASE_URL}/analytics/trends${query}`)
  );
}

export function usePerformanceTrends(params: { periods?: number; department?: string; period_id?: number } = {}) {
  const query = buildQueryString({
    limit: params.periods,
    department: params.department,
    period_id: params.period_id,
  });
  return useSWR<PerformanceTrendPoint[]>(
    [`${BASE_URL}/analytics/trends`, params],
    () => fetcher(`${BASE_URL}/analytics/trends${query}`)
  );
}

export function useScoreDistribution(params: { period_id?: number; department?: string } = {}) {
  const query = buildQueryString(params);
  return useSWR<ScoreDistributionSummary>(
    [`${BASE_URL}/analytics/distribution`, params],
    () => fetcher(`${BASE_URL}/analytics/distribution${query}`)
  );
}

export function useBonusEligibility(periodId: number, policyId?: number) {
  const query = buildQueryString({ period_id: periodId, policy_id: policyId });
  return useSWR<BonusEligibility[]>(
    [`${BASE_URL}/analytics/bonus-eligibility`, periodId, policyId],
    () => fetcher(`${BASE_URL}/analytics/bonus-eligibility${query}`)
  );
}

export function useKRABreakdown(params: { period_id?: number; department?: string } = {}) {
  const query = buildQueryString(params);
  return useSWR<KRABreakdown[]>(
    [`${BASE_URL}/analytics/kra-breakdown`, params],
    () => fetcher(`${BASE_URL}/analytics/kra-breakdown${query}`)
  );
}
