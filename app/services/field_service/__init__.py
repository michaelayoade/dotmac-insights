"""Field Service domain services.

This module provides services for managing field operations:
- ServiceOrderService: Service order CRUD and workflow
- ServiceTransactionService: Billing and invoicing for services
- FieldServiceBillingConfigService: Configurable rates and billing settings
- ScheduleService: Calendar views and availability checking
- TeamService: Team and technician management
- DispatchService: Dispatch board and bulk assignment

These services integrate with:
- Accounting: InvoiceService, ARPaymentService for billing
- Identity: Party system for customer linking
- Support: Ticket integration for repair orders
"""
from .service_orders import ServiceOrderService
from .transactions import ServiceTransactionService
from .billing_config import (
    FieldServiceBillingConfig,
    FieldServiceBillingConfigService,
    get_field_service_billing_config,
)
from .schedule import ScheduleService
from .teams import TeamService
from .dispatch import DispatchService
from .analytics import FieldServiceAnalyticsService
from .lookups import FieldServiceLookupService
from .analytics_types import (
    AnalyticsFilters,
    DashboardMetrics,
    OrderTypeBreakdown,
    PerformanceMetrics,
    TechnicianPerformance,
    TeamPerformance,
    MonthlyTrend,
    CostAnalysis,
    UtilizationMetrics,
)
from .schedule_types import (
    CalendarFilters,
    CalendarView,
    CalendarDay,
    TechnicianSchedule,
    TechnicianAvailability,
    AvailableTechnician,
)
from .dispatch_types import (
    DispatchBoardView,
    BulkAssignData,
    BulkAssignResult,
    RouteOptimizationResult,
)
from .team_types import (
    TeamFilters,
    TeamCreateData,
    TeamUpdateData,
    TeamMemberData,
    TechnicianFilters,
    TechnicianSkillData,
    ZoneFilters,
    ZoneCreateData,
    ZoneUpdateData,
)

from .service_types import (
    # Filters
    ServiceOrderFilters,
    TimeEntryFilters,
    # Create/Update DTOs
    ServiceOrderCreateData,
    ServiceOrderUpdateData,
    ServiceOrderItemData,
    TimeEntryData,
    ChecklistItemData,
    # Workflow DTOs
    DispatchData,
    CompletionData,
    RescheduleData,
    # Billing DTOs
    ServiceBillingData,
    ServiceInvoiceRequest,
    ServiceCostBreakdown,
    # Stats/Summary
    ServiceOrderStats,
    TechnicianWorkload,
    ZoneStats,
)

__all__ = [
    # Services
    "ServiceOrderService",
    "ServiceTransactionService",
    "ScheduleService",
    "TeamService",
    "DispatchService",
    "FieldServiceAnalyticsService",
    "FieldServiceLookupService",
    # Configuration
    "FieldServiceBillingConfig",
    "FieldServiceBillingConfigService",
    "get_field_service_billing_config",
    # Filters
    "ServiceOrderFilters",
    "TimeEntryFilters",
    # Create/Update DTOs
    "ServiceOrderCreateData",
    "ServiceOrderUpdateData",
    "ServiceOrderItemData",
    "TimeEntryData",
    "ChecklistItemData",
    # Workflow DTOs
    "DispatchData",
    "CompletionData",
    "RescheduleData",
    # Billing DTOs
    "ServiceBillingData",
    "ServiceInvoiceRequest",
    "ServiceCostBreakdown",
    # Stats/Summary
    "ServiceOrderStats",
    "TechnicianWorkload",
    "ZoneStats",
    # Analytics Types
    "AnalyticsFilters",
    "DashboardMetrics",
    "OrderTypeBreakdown",
    "PerformanceMetrics",
    "TechnicianPerformance",
    "TeamPerformance",
    "MonthlyTrend",
    "CostAnalysis",
    "UtilizationMetrics",
    # Schedule Types
    "CalendarFilters",
    "CalendarView",
    "CalendarDay",
    "TechnicianSchedule",
    "TechnicianAvailability",
    "AvailableTechnician",
    # Dispatch Types
    "DispatchBoardView",
    "BulkAssignData",
    "BulkAssignResult",
    "RouteOptimizationResult",
    # Team Types
    "TeamFilters",
    "TeamCreateData",
    "TeamUpdateData",
    "TeamMemberData",
    "TechnicianFilters",
    "TechnicianSkillData",
    "ZoneFilters",
    "ZoneCreateData",
    "ZoneUpdateData",
]
