"""Field Service models for technician dispatch and service order management."""
from __future__ import annotations

import enum
from datetime import datetime, date, time
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, Enum, Index, JSON, Date, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.project import Project
    from app.models.task import Task
    from app.models.ticket import Ticket
    from app.models.employee import Employee
    from app.models.asset import Asset
    from app.models.vehicle import Vehicle


# =============================================================================
# ENUMS
# =============================================================================

class ServiceOrderType(enum.Enum):
    """Type of field service order."""
    INSTALLATION = "installation"      # New project/customer setup
    REPAIR = "repair"                  # Support ticket field visit
    MAINTENANCE = "maintenance"        # Scheduled preventive maintenance
    INSPECTION = "inspection"          # Site survey/assessment
    RELOCATION = "relocation"          # Equipment move/upgrade
    UPGRADE = "upgrade"                # Service upgrade
    DISCONNECTION = "disconnection"    # Service termination


class ServiceOrderStatus(enum.Enum):
    """Status of service order lifecycle."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    DISPATCHED = "dispatched"
    EN_ROUTE = "en_route"
    ON_SITE = "on_site"
    IN_PROGRESS = "in_progress"
    PENDING_PARTS = "pending_parts"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"
    FAILED = "failed"


class ServiceOrderPriority(enum.Enum):
    """Priority level for service orders."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class TimeEntryType(enum.Enum):
    """Type of time entry."""
    TRAVEL = "travel"
    WORK = "work"
    BREAK = "break"
    WAITING = "waiting"


class PhotoType(enum.Enum):
    """Type of service photo."""
    BEFORE = "before"
    AFTER = "after"
    ISSUE = "issue"
    EQUIPMENT = "equipment"
    SIGNATURE = "signature"
    LOCATION = "location"


# =============================================================================
# SERVICE ZONES
# =============================================================================

class ServiceZone(Base):
    """Geographic service coverage zones."""
    __tablename__ = "service_zones"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Geographic bounds
    boundary_geojson: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    center_latitude: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    center_longitude: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    # Coverage cities/areas (JSON array)
    coverage_areas: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Default assignment
    default_team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("field_teams.id"), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    default_team: Mapped[Optional["FieldTeam"]] = relationship(back_populates="default_zones")

    def __repr__(self) -> str:
        return f"<ServiceZone {self.code}: {self.name}>"


# =============================================================================
# FIELD TEAMS
# =============================================================================

class FieldTeam(Base):
    """Field service teams."""
    __tablename__ = "field_teams"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Coverage configuration
    coverage_zone_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)
    max_daily_orders: Mapped[int] = mapped_column(default=10)

    # Contact
    supervisor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    members: Mapped[List["FieldTeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")
    supervisor: Mapped[Optional["Employee"]] = relationship(
        back_populates="supervised_field_teams",
        foreign_keys=[supervisor_id]
    )
    default_zones: Mapped[List["ServiceZone"]] = relationship(back_populates="default_team")
    service_orders: Mapped[List["ServiceOrder"]] = relationship(back_populates="team")

    def __repr__(self) -> str:
        return f"<FieldTeam {self.name}>"


class FieldTeamMember(Base):
    """Team member assignments."""
    __tablename__ = "field_team_members"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("field_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)

    # Role in team
    role: Mapped[str] = mapped_column(String(50), default="technician")  # lead, technician, helper

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    joined_date: Mapped[date] = mapped_column(default=date.today)

    # Relationships
    team: Mapped["FieldTeam"] = relationship(back_populates="members")
    employee: Mapped["Employee"] = relationship(back_populates="field_team_memberships")

    __table_args__ = (
        Index("ix_field_team_members_team_employee", "team_id", "employee_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<FieldTeamMember team={self.team_id} employee={self.employee_id}>"


# =============================================================================
# TECHNICIAN SKILLS
# =============================================================================

class TechnicianSkill(Base):
    """Skills and certifications for field technicians."""
    __tablename__ = "technician_skills"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)

    # Skill details
    skill_type: Mapped[str] = mapped_column(String(100), nullable=False)  # fiber, wireless, networking, electrical
    proficiency_level: Mapped[str] = mapped_column(String(50), default="intermediate")  # basic, intermediate, expert

    # Certification
    certification: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    certification_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    certification_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    certification_expiry: Mapped[Optional[date]] = mapped_column(nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee: Mapped["Employee"] = relationship(back_populates="technician_skills")

    __table_args__ = (
        Index("ix_technician_skills_employee_skill", "employee_id", "skill_type"),
    )

    def __repr__(self) -> str:
        return f"<TechnicianSkill {self.skill_type} ({self.proficiency_level})>"


# =============================================================================
# CHECKLIST TEMPLATES
# =============================================================================

class ChecklistTemplate(Base):
    """Templates for service order checklists."""
    __tablename__ = "checklist_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order_type: Mapped[ServiceOrderType] = mapped_column(Enum(ServiceOrderType), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    is_default: Mapped[bool] = mapped_column(default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items: Mapped[List["ChecklistTemplateItem"]] = relationship(back_populates="template", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChecklistTemplate {self.name}>"


class ChecklistTemplateItem(Base):
    """Items in a checklist template."""
    __tablename__ = "checklist_template_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("checklist_templates.id", ondelete="CASCADE"), nullable=False, index=True)

    # Item details
    idx: Mapped[int] = mapped_column(default=0)
    item_text: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Requirements
    is_required: Mapped[bool] = mapped_column(default=True)
    requires_photo: Mapped[bool] = mapped_column(default=False)
    requires_measurement: Mapped[bool] = mapped_column(default=False)
    measurement_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    template: Mapped["ChecklistTemplate"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<ChecklistTemplateItem {self.item_text[:30]}...>"


# =============================================================================
# SERVICE ORDERS
# =============================================================================

class ServiceOrder(Base):
    """Core field service order entity."""
    __tablename__ = "service_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # Type and status
    order_type: Mapped[ServiceOrderType] = mapped_column(Enum(ServiceOrderType), nullable=False, index=True)
    status: Mapped[ServiceOrderStatus] = mapped_column(Enum(ServiceOrderStatus), default=ServiceOrderStatus.DRAFT, index=True)
    priority: Mapped[ServiceOrderPriority] = mapped_column(Enum(ServiceOrderPriority), default=ServiceOrderPriority.MEDIUM, index=True)

    # Linked entities
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True, index=True)
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id"), nullable=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)

    # Asset/Vehicle links (for service history tracking)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assets.id"), nullable=True, index=True)
    vehicle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vehicles.id"), nullable=True, index=True)

    # Assignment
    assigned_technician_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    assigned_team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("field_teams.id"), nullable=True, index=True)
    zone_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service_zones.id"), nullable=True, index=True)

    # Location
    service_address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    # Scheduling
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    scheduled_end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    estimated_duration_hours: Mapped[Decimal] = mapped_column(default=Decimal("1"))

    # Actual times
    actual_start_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    actual_end_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    travel_start_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    arrival_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Work details
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    work_performed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Customer interaction
    customer_contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    customer_contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Base64
    customer_signature_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_signed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    customer_rating: Mapped[Optional[int]] = mapped_column(nullable=True)  # 1-5
    customer_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Costing
    labor_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    parts_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    travel_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    billable_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    is_billable: Mapped[bool] = mapped_column(default=True)

    # Notification tracking
    customer_notified: Mapped[bool] = mapped_column(default=False)
    last_notification_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Metadata
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped["Customer"] = relationship()
    project: Mapped[Optional["Project"]] = relationship()
    task: Mapped[Optional["Task"]] = relationship()
    ticket: Mapped[Optional["Ticket"]] = relationship()
    technician: Mapped[Optional["Employee"]] = relationship(
        back_populates="service_orders",
        foreign_keys=[assigned_technician_id]
    )
    team: Mapped[Optional["FieldTeam"]] = relationship(back_populates="service_orders")
    zone: Mapped[Optional["ServiceZone"]] = relationship()
    asset: Mapped[Optional["Asset"]] = relationship(backref="service_orders")
    vehicle_rel: Mapped[Optional["Vehicle"]] = relationship(backref="service_orders")
    checklist_items: Mapped[List["ServiceChecklist"]] = relationship(back_populates="service_order", cascade="all, delete-orphan")
    photos: Mapped[List["ServicePhoto"]] = relationship(back_populates="service_order", cascade="all, delete-orphan")
    time_entries: Mapped[List["ServiceTimeEntry"]] = relationship(back_populates="service_order", cascade="all, delete-orphan")
    items_used: Mapped[List["ServiceOrderItem"]] = relationship(back_populates="service_order", cascade="all, delete-orphan")
    status_history: Mapped[List["ServiceOrderStatusHistory"]] = relationship(back_populates="service_order", cascade="all, delete-orphan")
    notifications: Mapped[List["CustomerNotification"]] = relationship(back_populates="service_order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_service_orders_scheduled", "scheduled_date", "status"),
        Index("ix_service_orders_customer", "customer_id", "status"),
        Index("ix_service_orders_technician", "assigned_technician_id", "scheduled_date"),
    )

    def __repr__(self) -> str:
        return f"<ServiceOrder {self.order_number} - {self.status.value}>"

    @property
    def is_overdue(self) -> bool:
        """Check if order is overdue."""
        if self.status in [ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELLED]:
            return False
        return self.scheduled_date < date.today()

    @property
    def actual_duration_hours(self) -> Optional[Decimal]:
        """Calculate actual duration in hours."""
        if self.actual_start_time and self.actual_end_time:
            delta = self.actual_end_time - self.actual_start_time
            return Decimal(str(delta.total_seconds() / 3600))
        return None


class ServiceOrderStatusHistory(Base):
    """History of status changes for service orders."""
    __tablename__ = "service_order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True)

    # Status change
    from_status: Mapped[Optional[ServiceOrderStatus]] = mapped_column(Enum(ServiceOrderStatus), nullable=True)
    to_status: Mapped[ServiceOrderStatus] = mapped_column(Enum(ServiceOrderStatus), nullable=False)

    # Details
    changed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    # Timestamp
    changed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    # Relationship
    service_order: Mapped["ServiceOrder"] = relationship(back_populates="status_history")

    def __repr__(self) -> str:
        return f"<StatusHistory {self.from_status} -> {self.to_status}>"


# =============================================================================
# SERVICE CHECKLISTS
# =============================================================================

class ServiceChecklist(Base):
    """Checklist items for a service order."""
    __tablename__ = "service_checklists"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    template_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("checklist_template_items.id"), nullable=True)

    # Item details
    idx: Mapped[int] = mapped_column(default=0)
    item_text: Mapped[str] = mapped_column(String(500), nullable=False)
    is_required: Mapped[bool] = mapped_column(default=True)

    # Completion
    is_completed: Mapped[bool] = mapped_column(default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Notes and measurements
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    measurement_value: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    measurement_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Photo reference
    photo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service_photos.id"), nullable=True)

    # Relationship
    service_order: Mapped["ServiceOrder"] = relationship(back_populates="checklist_items")
    photo: Mapped[Optional["ServicePhoto"]] = relationship()

    def __repr__(self) -> str:
        return f"<ServiceChecklist {self.item_text[:30]}... {'[x]' if self.is_completed else '[ ]'}>"


# =============================================================================
# SERVICE PHOTOS
# =============================================================================

class ServicePhoto(Base):
    """Photos captured during field service."""
    __tablename__ = "service_photos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True)

    # Photo details
    photo_type: Mapped[PhotoType] = mapped_column(Enum(PhotoType), default=PhotoType.ISSUE)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Caption and metadata
    caption: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    # Timestamps
    captured_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    uploaded_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationship
    service_order: Mapped["ServiceOrder"] = relationship(back_populates="photos")

    def __repr__(self) -> str:
        return f"<ServicePhoto {self.photo_type.value}: {self.file_name}>"


# =============================================================================
# TIME ENTRIES
# =============================================================================

class ServiceTimeEntry(Base):
    """Time tracking for service orders."""
    __tablename__ = "service_time_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)

    # Entry type
    entry_type: Mapped[TimeEntryType] = mapped_column(Enum(TimeEntryType), default=TimeEntryType.WORK)

    # Times
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    duration_hours: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    # Details
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_billable: Mapped[bool] = mapped_column(default=True)

    # Location
    start_latitude: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    start_longitude: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    end_latitude: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    end_longitude: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    service_order: Mapped["ServiceOrder"] = relationship(back_populates="time_entries")
    employee: Mapped["Employee"] = relationship(back_populates="service_time_entries")

    def __repr__(self) -> str:
        return f"<ServiceTimeEntry {self.entry_type.value} - {self.duration_hours}h>"


# =============================================================================
# INVENTORY ITEMS USED
# =============================================================================

class ServiceOrderItem(Base):
    """Inventory items used in service orders."""
    __tablename__ = "service_order_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True)

    # Item reference
    stock_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("items.id"), nullable=True)
    item_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Quantity and cost
    quantity: Mapped[Decimal] = mapped_column(default=Decimal("1"))
    unit: Mapped[str] = mapped_column(String(50), default="pcs")
    unit_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Serial numbers (JSON array)
    serial_numbers: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Return tracking
    is_returned: Mapped[bool] = mapped_column(default=False)
    returned_quantity: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    return_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    added_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    added_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationship
    service_order: Mapped["ServiceOrder"] = relationship(back_populates="items_used")

    def __repr__(self) -> str:
        return f"<ServiceOrderItem {self.item_name} x{self.quantity}>"


# =============================================================================
# CUSTOMER NOTIFICATIONS
# =============================================================================

class CustomerNotificationType(enum.Enum):
    """Types of customer notifications."""
    # Service Order events
    SERVICE_SCHEDULED = "service_scheduled"
    SERVICE_RESCHEDULED = "service_rescheduled"
    SERVICE_CANCELLED = "service_cancelled"
    TECHNICIAN_ASSIGNED = "technician_assigned"
    TECHNICIAN_EN_ROUTE = "technician_en_route"
    TECHNICIAN_ARRIVED = "technician_arrived"
    SERVICE_STARTED = "service_started"
    SERVICE_COMPLETED = "service_completed"
    SERVICE_DELAYED = "service_delayed"

    # Ticket events
    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    TICKET_RESOLVED = "ticket_resolved"
    TICKET_REPLY = "ticket_reply"

    # Project events
    PROJECT_STARTED = "project_started"
    PROJECT_MILESTONE = "project_milestone"
    PROJECT_COMPLETED = "project_completed"

    # Invoice events
    INVOICE_GENERATED = "invoice_generated"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_DUE = "payment_due"

    # General
    CUSTOM = "custom"


class CustomerNotificationChannel(enum.Enum):
    """Channels for customer notifications."""
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    IN_APP = "in_app"
    PUSH = "push"


class CustomerNotificationStatus(enum.Enum):
    """Status of customer notification delivery."""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"


class CustomerNotification(Base):
    """Notifications sent to customers about their activities."""
    __tablename__ = "customer_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Target customer
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)

    # Notification details
    notification_type: Mapped[CustomerNotificationType] = mapped_column(Enum(CustomerNotificationType), nullable=False, index=True)
    channel: Mapped[CustomerNotificationChannel] = mapped_column(Enum(CustomerNotificationChannel), default=CustomerNotificationChannel.EMAIL)
    status: Mapped[CustomerNotificationStatus] = mapped_column(Enum(CustomerNotificationStatus), default=CustomerNotificationStatus.PENDING, index=True)

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    short_message: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)  # For SMS

    # Linked entities
    service_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service_orders.id"), nullable=True, index=True)
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id"), nullable=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id"), nullable=True)

    # Delivery details
    recipient_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recipient_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    recipient_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Metadata
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Delivery tracking
    attempt_count: Mapped[int] = mapped_column(default=0)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # External reference
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # SMS provider ID, etc.

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship()
    service_order: Mapped[Optional["ServiceOrder"]] = relationship(back_populates="notifications")

    __table_args__ = (
        Index("ix_customer_notifications_customer_type", "customer_id", "notification_type"),
        Index("ix_customer_notifications_status", "status", "scheduled_at"),
    )

    def __repr__(self) -> str:
        return f"<CustomerNotification {self.notification_type.value} -> {self.customer_id}>"


# =============================================================================
# CUSTOMER NOTIFICATION PREFERENCES
# =============================================================================

class CustomerNotificationPreference(Base):
    """Customer preferences for notifications."""
    __tablename__ = "customer_notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)

    # Event type
    notification_type: Mapped[CustomerNotificationType] = mapped_column(Enum(CustomerNotificationType), nullable=False)

    # Channel preferences
    email_enabled: Mapped[bool] = mapped_column(default=True)
    sms_enabled: Mapped[bool] = mapped_column(default=False)
    whatsapp_enabled: Mapped[bool] = mapped_column(default=False)
    push_enabled: Mapped[bool] = mapped_column(default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_customer_notif_prefs_customer_type", "customer_id", "notification_type", unique=True),
    )

    def __repr__(self) -> str:
        return f"<CustomerNotificationPreference {self.notification_type.value} for customer={self.customer_id}>"
