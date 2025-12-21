/**
 * Domain APIs Barrel Export
 *
 * This file exports all domain-specific APIs for easy importing.
 * Each domain is self-contained with its types and API methods.
 */

// Admin Domain (Sync, Explorer, Settings)
export { adminApi } from './admin';
export type {
  SyncSourceStatus,
  SyncStatus,
  SyncLog,
  TableInfo,
  EnhancedTableInfo,
  TablesResponse,
  ExploreTableResponse,
  DataQuality,
  SettingsGroupMeta,
  SettingsResponse,
  SettingsSchemaResponse,
  SettingsTestResponse,
  SettingsAuditEntry,
  PermissionResponse,
  RoleResponse,
  RoleCreatePayload,
  RoleUpdatePayload,
} from './admin';

// Projects Domain
export { projectsApi } from './projects';
export type {
  ProjectStatus,
  ProjectPriority,
  ProjectUser,
  ProjectListItem,
  ProjectListResponse,
  ProjectDetail,
  ProjectPayload,
  ProjectsDashboard,
  ProjectTaskListResponse,
  ProjectListParams,
  ProjectTaskParams,
} from './projects';

// CRM Domain (Leads, Opportunities, Activities, Contacts, Pipeline)
export { crmApi } from './crm';
export type {
  Lead,
  LeadListResponse,
  LeadSummaryResponse,
  LeadCreatePayload,
  LeadConvertPayload,
  LeadConvertResponse,
  LeadListParams,
  OpportunityStage,
  Opportunity,
  OpportunityListResponse,
  PipelineSummaryResponse,
  OpportunityCreatePayload,
  OpportunityListParams,
  Activity,
  ActivityListResponse,
  ActivitySummaryResponse,
  ActivityCreatePayload,
  ActivityListParams,
  ActivityTimelineParams,
  ActivityTimelineResponse,
  Contact,
  ContactListResponse,
  ContactCreatePayload,
  ContactListParams,
  ContactsByEntityResponse,
  PipelineStage,
  PipelineViewResponse,
  KanbanColumn,
  KanbanViewResponse,
  PipelineStageCreatePayload,
  PipelineStageUpdatePayload,
  SuccessResponse as CrmSuccessResponse,
  SeedDefaultStagesResponse,
} from './crm';

// Also export standalone functions for backward compatibility
export {
  getLeads,
  getLeadsSummary,
  getLead,
  createLead,
  updateLead,
  convertLead,
  qualifyLead,
  disqualifyLead,
  getOpportunities,
  getPipelineSummary,
  getOpportunity,
  createOpportunity,
  updateOpportunity,
  moveOpportunityStage,
  markOpportunityWon,
  markOpportunityLost,
  getActivities,
  getActivitiesSummary,
  getActivityTimeline,
  getActivity,
  createActivity,
  updateActivity,
  completeActivity,
  cancelActivity,
  deleteActivity,
  getContacts,
  getCustomerContacts,
  getLeadContacts,
  getContact,
  createContact,
  updateContact,
  setContactPrimary,
  deleteContact,
  getPipelineStages,
  getPipelineView,
  getKanbanView,
  createPipelineStage,
  updatePipelineStage,
  reorderPipelineStages,
  deletePipelineStage,
  seedDefaultPipelineStages,
} from './crm';

// Customers Domain
export { customersApi } from './customers';
export type {
  CustomerDashboard,
  Customer,
  CustomerListResponse,
  CustomerDetail,
  BlockedCustomer,
  BlockedCustomersResponse,
  CustomerWritePayload,
  CustomerSubscriptionPayload,
  CustomerInvoicePayload,
  CustomerPaymentPayload,
  CustomerUsageTotals,
  CustomerUsageDaily,
  CustomerUsageBySubscription,
  CustomerUsageResponse,
  Customer360Profile,
  Customer360Finance,
  Customer360Services,
  Customer360Network,
  Customer360Support,
  Customer360Projects,
  Customer360CRM,
  Customer360TimelineItem,
  Customer360Response,
  CustomerSignupTrendResponse,
  CustomerCohortItem,
  CustomerCohortResponse,
  CustomerByPlanItem,
  CustomerByType,
  CustomerByLocation,
  CustomerByTypeResponse,
  CustomerByLocationResponse,
  CustomerByPop,
  CustomerByRouter,
  CustomerTicketVolumeBucket,
  CustomerDataQualityOutreach,
  CustomerRevenueOverdue,
  ActiveAnalyticsResponse,
  CustomerPaymentTimeliness,
  CustomerSegmentsInsightsResponse,
  CustomerHealthInsightsResponse,
  CustomerCompletenessField,
  CustomerCompletenessResponse,
  CustomerPlanChange,
  CustomerPlanChangesResponse,
  CustomerSegment,
  CustomerSegmentsResponse,
  CustomerHealthRecord,
  CustomerHealthResponse,
  CustomerListParams,
  BlockedCustomerParams,
  CustomerSignupTrendParams,
} from './customers';

// Support Domain (Tickets, Agents, Teams, SLA, Automation, KB, CSAT)
export { supportApi } from './support';
export type {
  SupportMetrics,
  SupportTicketComment,
  SupportTicketCommentPayload,
  SupportTicketActivity,
  SupportTicketActivityPayload,
  SupportTicketCommunication,
  SupportTicketCommunicationPayload,
  SupportTicketDependency,
  SupportTicketDependencyPayload,
  SupportTicketExpense,
  SupportTicketDetail,
  SupportSettingsResponse,
  SupportSettingsUpdate,
  WorkingHoursType,
  DefaultRoutingStrategy,
  TicketAutoCloseAction,
  CSATSurveyTrigger,
  TicketPriorityDefault,
  NotificationChannel,
  WeeklyScheduleDay,
  SupportTicketPayload,
  SupportTicketAssigneePayload,
  SupportTicketSlaPayload,
  SupportTicketListItem,
  SupportTicketListResponse,
  SupportTicketListParams,
  SupportTicketCreateResponse,
  SupportOverviewRequest,
  SupportOverviewResponse,
  SupportAgent,
  SupportAgentPayload,
  SupportTeam,
  SupportTeamMember,
  SupportTeamPayload,
  SupportTeamMemberPayload,
  SupportVolumeTrend,
  SupportResolutionTimeTrend,
  SupportCategoryBreakdown,
  SupportSlaPerformanceTrend,
  SupportPatterns,
  SupportAgentPerformanceInsights,
  SupportCsatSurvey,
  SupportCsatSummary,
  SupportCsatAgentPerformance,
  SupportCsatTrend,
  SupportAutomationRule,
  SupportAutomationLog,
  SupportAutomationLogList,
  SupportAutomationLogSummary,
  SupportAutomationReference,
  SupportCalendar,
  SupportSlaPolicy,
  SupportSlaBreachSummary,
  SupportRoutingRule,
  SupportQueueHealth,
  SupportAgentWorkload,
  SupportKbCategory,
  SupportKbArticle,
  SupportKbArticleList,
  SupportCannedResponse,
  SupportCannedResponseList,
} from './support';

// Expenses Domain (Claims, Advances, Cards, Transactions, Statements)
export { expensesApi } from './expenses';
export * from './expenses';

// Finance Domain (Sales/AR - Invoices, Payments, Credit Notes, Orders, Quotations)
export { financeApi } from './finance';
export type {
  FinanceDashboard,
  FinanceInvoice,
  FinanceInvoiceItem,
  FinanceInvoicePaymentRef,
  FinanceInvoiceCreditNoteRef,
  FinanceInvoiceDetail,
  FinanceInvoiceListResponse,
  FinanceInvoicePayload,
  FinanceInvoiceListParams,
  FinancePayment,
  FinancePaymentReference,
  FinancePaymentDetail,
  FinancePaymentListResponse,
  FinancePaymentPayload,
  FinancePaymentListParams,
  FinanceCreditNote,
  FinanceCreditNoteDetail,
  FinanceCreditNoteListResponse,
  FinanceCreditNotePayload,
  FinanceCreditNoteListParams,
  FinanceOrder,
  FinanceOrderItem,
  FinanceOrderListResponse,
  FinanceOrderPayload,
  FinanceOrderListParams,
  FinanceQuotation,
  FinanceQuotationItem,
  FinanceQuotationListResponse,
  FinanceQuotationPayload,
  FinanceQuotationListParams,
  FinanceCustomerPayload,
  FinanceRevenueTrend,
  FinanceCollectionsAnalytics,
  FinanceAgingBucket,
  FinanceAgingAnalytics,
  FinanceByCurrencyAnalytics,
  FinancePaymentBehavior,
  FinanceForecast,
} from './finance';

// Accounting Domain (GL, Journals, Bank Transactions, Financial Statements, Tax)
export { accountingApi } from './accounting';
export type {
  // IFRS Compliance
  ValidationIssue,
  ValidationResult,
  FXMetadata,
  ComparativePeriod,
  EarningsPerShare,
  TaxReconciliation,
  OCIComponent,
  OtherComprehensiveIncome,
  NonCashTransactionType,
  NonCashTransaction,
  CashFlowClassificationPolicy,
  // Dashboard & Accounts
  AccountingDashboard,
  AccountingAccount,
  AccountingAccountTreeNode,
  AccountingChartOfAccounts,
  AccountingAccountDetail,
  AccountingAccountPayload,
  // General Ledger
  AccountingGeneralLedgerEntry,
  AccountingGeneralLedgerResponse,
  // Journal Entries
  AccountingJournalEntryLine,
  AccountingJournalEntryPayload,
  AccountingJournalEntry,
  AccountingJournalEntryListResponse,
  // Financial Statements
  AccountingTrialBalance,
  AccountingBalanceSheet,
  AccountingIncomeStatement,
  AccountingCashFlow,
  AccountingEquityStatement,
  AccountingFinancialRatios,
  // AP & AR
  AccountingPayable,
  AccountingPayableResponse,
  AccountingReceivable,
  AccountingReceivableResponse,
  AccountingOutstandingSummary,
  // Suppliers
  AccountingSupplier,
  AccountingSupplierListResponse,
  AccountingSupplierPayload,
  // Bank Accounts & Transactions
  AccountingBankAccount,
  AccountingBankAccountListResponse,
  AccountingBankAccountPayload,
  AccountingBankTransaction,
  AccountingBankTransactionListResponse,
  AccountingBankTransactionPayment,
  AccountingBankTransactionDetail,
  BankTransactionCreatePayload,
  BankTransactionCreateResponse,
  BankTransactionImportResponse,
  ReconciliationSuggestion,
  BankTransactionSuggestionsResponse,
  ReconcilePayload,
  ReconcileResponse,
  // Purchase Invoices
  AccountingPurchaseInvoice,
  AccountingPurchaseInvoiceDetail,
  AccountingPurchaseInvoiceListResponse,
  // Fiscal Years & Cost Centers
  AccountingFiscalYear,
  AccountingFiscalYearListResponse,
  AccountingCostCenter,
  AccountingCostCenterListResponse,
  // Tax Templates
  AccountingTaxCategory,
  AccountingTaxTemplate,
  AccountingTaxSummary,
  // Nigerian Tax Module
  NigerianTaxType,
  TaxJurisdiction,
  WHTPaymentType,
  CITCompanySize,
  VATTransactionType,
  EInvoiceStatus,
  PAYEFilingFrequency,
  TaxSettings,
  TaxDashboard,
  VATTransaction,
  VATTransactionsResponse,
  VATOutputPayload,
  VATInputPayload,
  VATSummary,
  VATFilingPrep,
  WHTTransaction,
  WHTTransactionsResponse,
  WHTDeductPayload,
  WHTSupplierSummary,
  WHTRemittanceDue,
  WHTCertificate,
  WHTCertificatePayload,
  PAYECalculation,
  PAYECalculationsResponse,
  PAYECalculatePayload,
  PAYESummary,
  CITAssessment,
  CITAssessmentsResponse,
  CITAssessmentPayload,
  CITComputation,
  CITRateResult,
  FilingDeadline,
  FilingCalendar,
  EInvoice,
  EInvoicesResponse,
  EInvoicePayload,
  EInvoiceValidation,
  EInvoiceUBL,
  // Params
  AccountingChartOfAccountsParams,
  AccountingAccountDetailParams,
  AccountingGeneralLedgerParams,
  AccountingJournalEntryListParams,
  AccountingBankTransactionListParams,
  AccountingPurchaseInvoiceListParams,
  AccountingSupplierListParams,
} from './accounting';

// Purchasing Domain (AP - Bills, Payments, Orders, Debit Notes, Suppliers, Expenses)
export { purchasingApi } from './purchasing';
export type {
  // Dashboard
  PurchasingDashboard,
  // Bills
  PurchasingBill,
  PurchasingBillListResponse,
  PurchasingBillItem,
  PurchasingBillGLEntry,
  PurchasingBillDetail,
  PurchasingBillPayload,
  PurchasingBillListParams,
  // Payments
  PurchasingPayment,
  PurchasingPaymentListResponse,
  PurchasingPaymentDetail,
  PurchasingPaymentListParams,
  // Orders
  PurchasingOrder,
  PurchasingOrderListResponse,
  PurchasingOrderItem,
  PurchasingOrderDetail,
  PurchasingOrderPayload,
  PurchasingOrderListParams,
  // Debit Notes
  PurchasingDebitNote,
  PurchasingDebitNoteListResponse,
  PurchasingDebitNoteItem,
  PurchasingDebitNoteDetail,
  PurchasingDebitNotePayload,
  PurchasingDebitNoteListParams,
  // Suppliers
  PurchasingSupplier,
  PurchasingSupplierListResponse,
  PurchasingSupplierRecentBill,
  PurchasingSupplierDetail,
  PurchasingSupplierGroupsResponse,
  PurchasingSupplierListParams,
  // Expenses
  PurchasingExpense,
  PurchasingExpenseListResponse,
  PurchasingExpenseDetail,
  PurchasingExpensePayload,
  PurchasingExpenseTypesResponse,
  PurchasingExpenseListParams,
  // ERPNext Expense Claims
  ERPNextExpenseClaim,
  ERPNextExpenseClaimListResponse,
  ERPNextExpenseClaimDetail,
  ERPNextExpenseClaimPayload,
  ERPNextExpenseClaimListParams,
  // Analytics
  PurchasingAgingInvoice,
  PurchasingAgingBucket,
  PurchasingAgingResponse,
  PurchasingBySupplierItem,
  PurchasingBySupplierResponse,
  PurchasingByCostCenterItem,
  PurchasingByCostCenterResponse,
  PurchasingExpenseTrendItem,
  PurchasingExpenseTrendResponse,
} from './purchasing';

// HR Domain (Employees, Leave, Attendance, Payroll, Training, Appraisals, Lifecycle)
export { hrApi } from './hr';
export type {
  // Generic
  HrListResponse,
  // Leave Management
  HrLeaveType,
  HrHolidayItem,
  HrHolidayListPayload,
  HrHolidayList,
  HrLeavePolicyDetail,
  HrLeavePolicyPayload,
  HrLeavePolicy,
  HrLeaveAllocationPayload,
  HrLeaveAllocation,
  HrLeaveApplicationPayload,
  HrLeaveApplication,
  // Attendance & Shifts
  HrShiftType,
  HrShiftAssignmentPayload,
  HrShiftAssignment,
  HrAttendancePayload,
  HrAttendance,
  HrAttendanceRequestPayload,
  HrAttendanceRequest,
  // Recruitment
  HrJobOpeningPayload,
  HrJobOpening,
  HrJobApplicantPayload,
  HrJobApplicant,
  HrJobOfferTerm,
  HrJobOfferPayload,
  HrJobOffer,
  HrInterviewPayload,
  HrInterview,
  // Payroll
  HrSalaryComponentPayload,
  HrSalaryComponent,
  HrSalaryStructureLine,
  HrSalaryStructurePayload,
  HrSalaryStructure,
  HrSalaryStructureAssignmentPayload,
  HrSalaryStructureAssignment,
  HrPayrollEntryPayload,
  HrPayrollEntry,
  HrSalarySlipPayload,
  HrSalarySlip,
  HrPayrollPayoutItem,
  HrPayrollPayoutRequest,
  HRSettingsResponse,
  HRSettingsUpdate,
  LeaveAccountingFrequency,
  ProRataMethod,
  PayrollFrequency,
  OvertimeCalculation,
  GratuityCalculation,
  AttendanceMarkingMode,
  AppraisalFrequency,
  EmployeeIDFormat,
  WeekDay,
  // Training
  HrTrainingProgramPayload,
  HrTrainingProgram,
  HrTrainingEventEmployee,
  HrTrainingEventPayload,
  HrTrainingEvent,
  HrTrainingResultPayload,
  HrTrainingResult,
  // Appraisals
  HrAppraisalTemplateGoal,
  HrAppraisalTemplatePayload,
  HrAppraisalTemplate,
  HrAppraisalGoal,
  HrAppraisalPayload,
  HrAppraisal,
  // Employee Lifecycle
  HrOnboardingActivity,
  HrEmployeeOnboardingPayload,
  HrEmployeeOnboarding,
  HrSeparationActivity,
  HrEmployeeSeparationPayload,
  HrEmployeeSeparation,
  HrEmployeePromotionDetail,
  HrEmployeePromotionPayload,
  HrEmployeePromotion,
  HrEmployeeTransferDetail,
  HrEmployeeTransferPayload,
  HrEmployeeTransfer,
  // Analytics
  HrAnalyticsOverview,
  HrLeaveTrendPoint,
  HrAttendanceTrendPoint,
  HrPayrollSummary,
  HrPayrollTrendPoint,
  HrPayrollComponentBreakdown,
  HrRecruitmentFunnel,
  HrAppraisalStatusBreakdown,
  HrLifecycleEventsBreakdown,
  HrEmployee,
  HrEmployeeListResponse,
  // Params
  HrLeaveTypeListParams,
  HrHolidayListParams,
  HrLeaveAllocationListParams,
  HrLeaveApplicationListParams,
  HrAttendanceListParams,
  HrJobOpeningListParams,
  HrJobApplicantListParams,
  HrPayrollEntryListParams,
  HrTrainingEventListParams,
  HrAppraisalListParams,
} from './hr';

// Analytics Domain (Cross-Domain Reports)
export { analyticsApi } from './analytics';
export type {
  // Revenue Reports
  ReportsRevenueSummary,
  ReportsRevenueTrendPoint,
  ReportsRevenueByCustomer,
  ReportsRevenueByProduct,
  // Expense Reports
  ReportsExpensesSummary,
  ReportsExpenseTrendPoint,
  ReportsExpenseByCategory,
  ReportsExpenseByVendor,
  // Profitability Reports
  ReportsProfitabilityMargins,
  ReportsProfitabilityTrendPoint,
  ReportsProfitabilityBySegment,
  // Cash Position Reports
  ReportsCashPositionSummary,
  ReportsCashPositionForecastPoint,
  ReportsCashPositionRunway,
} from './analytics';

// Insights Domain (Deep Insights, Data Quality, Anomalies)
export { insightsApi } from './insights';
export type {
  // Data Completeness
  FieldCompleteness,
  EntityCompleteness,
  DataCompletenessResponse,
  // Customer Segments (Deep)
  InsightsCustomerSegment,
  InsightsCustomerSegmentsResponse,
  // Customer Health (Deep)
  InsightsCustomerHealthRecord,
  InsightsCustomerHealthResponse,
  // Relationship Map
  EntityRelationship,
  RelationshipMapResponse,
  // Financial Insights
  FinancialInsightsResponse,
  // Operational Insights
  OperationalInsightsResponse,
  // Anomalies
  Anomaly,
  AnomaliesResponse,
  // Data Availability
  DataAvailabilityEntity,
  DataAvailabilityGap,
  DataAvailabilityResponse,
  // Churn Risk
  ChurnRiskCustomer,
  ChurnRiskSummary,
  ChurnRiskResponse,
} from './insights';

// Webhooks Domain (Outbound, Inbound, OmniChannel)
export { webhooksApi } from './webhooks';
export * from './webhooks';

// Field Service Domain (Orders, Teams, Technicians, Schedule, Analytics)
export { fieldServiceApi } from './fieldService';
export * from './fieldService';

// Payments Domain (Gateway, Transfers, Open Banking)
export { paymentsApi } from './payments';
export * from './payments';

// Documents Domain (Attachments, Number Formats)
export { documentsApi } from './documents';
export * from './documents';

// Inventory Domain (Items, Warehouses, Stock, Batches, Serials, Transfers)
export { inventoryApi } from './inventory';
export * from './inventory';

// Assets Domain (Fixed Assets, Categories, Depreciation, Maintenance)
export { assetsApi } from './assets';
export * from './assets';

// Inbox Domain (Omnichannel - Conversations, Contacts, Routing Rules, Analytics)
export { inboxApi } from './inbox';
export * from './inbox';

// Sales Domain (Customer Groups, Territories, Sales Persons)
export { salesApi } from './sales';
export type {
  CustomerGroup,
  CustomerGroupListResponse,
  CustomerGroupPayload,
  Territory,
  TerritoryListResponse,
  TerritoryPayload,
  SalesPerson,
  SalesPersonListResponse,
  SalesPersonPayload,
} from './sales';

// Fleet Management Domain (Vehicles, Driver Assignments, Insurance)
export { fleetApi } from './fleet';
export type {
  Vehicle,
  VehicleListResponse,
  VehicleSummary,
  VehicleUpdatePayload,
  VehicleListParams,
} from './fleet';

// Consolidated Dashboards Domain (Single-Payload Dashboards)
export { dashboardsApi } from './dashboards';
export type {
  SalesDashboardResponse,
  PurchasingDashboardResponse,
  SupportDashboardResponse as SupportDashboardAggregateResponse,
  FieldServiceDashboardResponse,
  AccountingDashboardResponse,
} from './dashboards';
