"""Type definitions for field service operations.

These dataclasses define the contract for field service operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Dict, List, Optional

__all__ = [
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


# =============================================================================
# FILTERS
# =============================================================================

@dataclass
class ServiceOrderFilters:
    """Filters for listing service orders."""

    search: Optional[str] = None
    order_type: Optional[str] = None  # installation, repair, maintenance, etc.
    status: Optional[str] = None
    statuses: Optional[List[str]] = None
    priority: Optional[str] = None
    customer_account_id: Optional[int] = None
    technician_id: Optional[int] = None
    team_id: Optional[int] = None
    zone_id: Optional[int] = None
    scheduled_date_from: Optional[date] = None
    scheduled_date_to: Optional[date] = None
    is_billable: Optional[bool] = None
    is_billed: Optional[bool] = None
    city: Optional[str] = None
    sort_by: str = "scheduled_date"
    sort_dir: str = "desc"


@dataclass
class TimeEntryFilters:
    """Filters for time entries."""

    service_order_id: Optional[int] = None
    employee_id: Optional[int] = None
    entry_type: Optional[str] = None  # travel, work, break, waiting
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    is_billable: Optional[bool] = None


# =============================================================================
# CREATE/UPDATE DTOs
# =============================================================================

@dataclass
class ServiceOrderItemData:
    """Data for service order items (parts/materials)."""

    item_name: str
    quantity: Decimal = Decimal("1")
    unit: str = "pcs"
    unit_cost: Decimal = Decimal("0")
    item_code: Optional[str] = None
    stock_item_id: Optional[int] = None
    serial_numbers: Optional[List[str]] = None


@dataclass
class TimeEntryData:
    """Data for time entries."""

    entry_type: str  # travel, work, break, waiting
    start_time: datetime
    end_time: Optional[datetime] = None
    employee_id: Optional[int] = None
    notes: Optional[str] = None
    is_billable: bool = True
    start_latitude: Optional[Decimal] = None
    start_longitude: Optional[Decimal] = None
    end_latitude: Optional[Decimal] = None
    end_longitude: Optional[Decimal] = None


@dataclass
class ChecklistItemData:
    """Data for checklist items."""

    item_text: str
    is_required: bool = True
    idx: int = 0
    template_item_id: Optional[int] = None
    requires_photo: bool = False
    requires_measurement: bool = False
    measurement_unit: Optional[str] = None


@dataclass
class ServiceOrderCreateData:
    """Data for creating a service order."""

    customer_account_id: int
    order_type: str  # installation, repair, maintenance, etc.
    title: str
    service_address: str
    scheduled_date: date

    # Optional fields
    description: Optional[str] = None
    priority: str = "medium"
    scheduled_start_time: Optional[time] = None
    scheduled_end_time: Optional[time] = None
    estimated_duration_hours: Decimal = Decimal("1")

    # Location
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    # Linked entities
    project_id: Optional[int] = None
    task_id: Optional[int] = None
    ticket_id: Optional[int] = None
    asset_id: Optional[int] = None

    # Assignment
    assigned_technician_id: Optional[int] = None
    assigned_team_id: Optional[int] = None
    zone_id: Optional[int] = None

    # Customer contact
    customer_contact_name: Optional[str] = None
    customer_contact_phone: Optional[str] = None
    customer_contact_email: Optional[str] = None

    # Billing
    is_billable: bool = True
    billable_amount: Decimal = Decimal("0")

    # Items and checklist
    items: List[ServiceOrderItemData] = field(default_factory=list)
    checklist: List[ChecklistItemData] = field(default_factory=list)


@dataclass
class ServiceOrderUpdateData:
    """Data for updating a service order (all fields optional)."""

    title: Optional[str] = None
    description: Optional[str] = None
    order_type: Optional[str] = None
    priority: Optional[str] = None
    service_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    scheduled_date: Optional[date] = None
    scheduled_start_time: Optional[time] = None
    scheduled_end_time: Optional[time] = None
    estimated_duration_hours: Optional[Decimal] = None
    assigned_technician_id: Optional[int] = None
    assigned_team_id: Optional[int] = None
    zone_id: Optional[int] = None
    customer_contact_name: Optional[str] = None
    customer_contact_phone: Optional[str] = None
    customer_contact_email: Optional[str] = None
    is_billable: Optional[bool] = None
    billable_amount: Optional[Decimal] = None


# =============================================================================
# WORKFLOW DTOs
# =============================================================================

@dataclass
class DispatchData:
    """Data for dispatching a service order."""

    technician_id: int
    team_id: Optional[int] = None
    scheduled_date: Optional[date] = None
    scheduled_start_time: Optional[time] = None
    notes: Optional[str] = None


@dataclass
class CompletionData:
    """Data for completing a service order."""

    work_performed: str
    resolution_notes: Optional[str] = None
    actual_end_time: Optional[datetime] = None

    # Customer sign-off
    customer_signature: Optional[str] = None  # Base64
    customer_signature_name: Optional[str] = None
    customer_rating: Optional[int] = None  # 1-5
    customer_feedback: Optional[str] = None

    # Items used during service
    items_used: List[ServiceOrderItemData] = field(default_factory=list)

    # Final time entries
    time_entries: List[TimeEntryData] = field(default_factory=list)


@dataclass
class RescheduleData:
    """Data for rescheduling a service order."""

    new_date: date
    new_start_time: Optional[time] = None
    new_end_time: Optional[time] = None
    reason: str = ""
    notify_customer: bool = True


# =============================================================================
# BILLING DTOs
# =============================================================================

@dataclass
class ServiceCostBreakdown:
    """Breakdown of service order costs."""

    labor_cost: Decimal = Decimal("0")
    labor_hours: Decimal = Decimal("0")
    labor_rate: Decimal = Decimal("0")

    parts_cost: Decimal = Decimal("0")
    parts_count: int = 0

    travel_cost: Decimal = Decimal("0")
    travel_hours: Decimal = Decimal("0")
    travel_rate: Decimal = Decimal("0")

    other_costs: Decimal = Decimal("0")

    subtotal: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total: Decimal = Decimal("0")

    # Line items for invoice
    line_items: List[Dict] = field(default_factory=list)


@dataclass
class ServiceBillingData:
    """Billing configuration for a service order."""

    service_order_id: int
    is_billable: bool = True

    # Override amounts (if not calculated)
    labor_cost_override: Optional[Decimal] = None
    parts_cost_override: Optional[Decimal] = None
    travel_cost_override: Optional[Decimal] = None
    total_override: Optional[Decimal] = None

    # Rates
    hourly_labor_rate: Optional[Decimal] = None
    hourly_travel_rate: Optional[Decimal] = None

    # Tax
    tax_rate: Optional[Decimal] = None

    # Discounts
    discount_percent: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    discount_reason: Optional[str] = None


@dataclass
class ServiceInvoiceRequest:
    """Request to generate invoice from service order(s)."""

    service_order_ids: List[int]
    customer_account_id: int
    party_id: Optional[int] = None

    # Invoice details
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: str = "NGN"
    notes: Optional[str] = None

    # Billing overrides
    billing_overrides: Dict[int, ServiceBillingData] = field(default_factory=dict)

    # Options
    combine_line_items: bool = False  # Combine into single line or itemize
    include_parts_detail: bool = True
    include_time_detail: bool = False
    auto_post: bool = False


# =============================================================================
# STATS/SUMMARY
# =============================================================================

@dataclass
class ServiceOrderStats:
    """Statistics for service orders."""

    total: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    by_priority: Dict[str, int] = field(default_factory=dict)

    # Completion metrics
    completed_today: int = 0
    completed_this_week: int = 0
    completed_this_month: int = 0

    # Overdue
    overdue_count: int = 0

    # Financial
    total_billable: Decimal = Decimal("0")
    total_billed: Decimal = Decimal("0")
    unbilled_amount: Decimal = Decimal("0")

    # Time metrics
    avg_completion_time_hours: Optional[Decimal] = None
    total_labor_hours: Decimal = Decimal("0")
    total_travel_hours: Decimal = Decimal("0")


@dataclass
class TechnicianWorkload:
    """Workload summary for a technician."""

    technician_id: int
    technician_name: str

    # Assignments
    total_assigned: int = 0
    scheduled_today: int = 0
    scheduled_this_week: int = 0
    in_progress: int = 0
    completed_this_week: int = 0

    # Utilization
    total_hours_this_week: Decimal = Decimal("0")
    billable_hours_this_week: Decimal = Decimal("0")
    utilization_percent: Decimal = Decimal("0")

    # Performance
    avg_completion_time_hours: Optional[Decimal] = None
    avg_customer_rating: Optional[Decimal] = None


@dataclass
class ZoneStats:
    """Statistics for a service zone."""

    zone_id: int
    zone_name: str
    zone_code: str

    # Orders
    total_orders: int = 0
    pending_orders: int = 0
    completed_orders: int = 0

    # Technicians
    technician_count: int = 0
    available_technicians: int = 0

    # Financial
    total_revenue: Decimal = Decimal("0")
    avg_order_value: Decimal = Decimal("0")
