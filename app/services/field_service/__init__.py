"""Field Service domain services.

This module provides services for managing field operations:
- ServiceOrderService: Service order CRUD and workflow
- ServiceTransactionService: Billing and invoicing for services
- FieldServiceBillingConfigService: Configurable rates and billing settings

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
]
