"""Support/Helpdesk Settings API Endpoints

Endpoints for managing support configuration including SLA defaults, routing,
escalation policies, queues, and notification settings.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require
from app.models.support_settings import (
    SupportSettings, EscalationPolicy, EscalationLevel, SupportQueue,
    TicketFieldConfig, SupportEmailTemplate,
    DefaultRoutingStrategy, TicketAutoCloseAction, CSATSurveyTrigger,
    WorkingHoursType, EscalationTrigger, TicketPriorityDefault
)

router = APIRouter(prefix="/support/settings", tags=["support-settings"])


def _apply_updates(target: Any, updates: Dict[str, Any]) -> None:
    for field, value in updates.items():
        setattr(target, field, value)


# =============================================================================
# SCHEMAS
# =============================================================================

class WeeklyScheduleDay(BaseModel):
    start: str = "09:00"
    end: str = "17:00"
    closed: bool = False


class SupportSettingsResponse(BaseModel):
    id: int
    company: Optional[str]

    # Business Hours
    working_hours_type: WorkingHoursType
    timezone: str
    weekly_schedule: Dict[str, Any]
    holiday_calendar_id: Optional[int]

    # SLA Defaults
    default_sla_policy_id: Optional[int]
    sla_warning_threshold_percent: int
    sla_include_holidays: bool
    sla_include_weekends: bool
    default_first_response_hours: Decimal
    default_resolution_hours: Decimal

    # Ticket Routing
    default_routing_strategy: DefaultRoutingStrategy
    default_team_id: Optional[int]
    fallback_team_id: Optional[int]
    auto_assign_enabled: bool
    max_tickets_per_agent: int
    rebalance_threshold_percent: int

    # Ticket Defaults
    default_priority: TicketPriorityDefault
    default_ticket_type: Optional[str]
    allow_customer_priority_selection: bool
    allow_customer_team_selection: bool

    # Auto-Close
    auto_close_enabled: bool
    auto_close_resolved_days: int
    auto_close_action: TicketAutoCloseAction
    auto_close_notify_customer: bool
    allow_customer_reopen: bool
    reopen_window_days: int
    max_reopens_allowed: int

    # Escalation
    escalation_enabled: bool
    default_escalation_team_id: Optional[int]
    escalation_notify_manager: bool
    idle_escalation_enabled: bool
    idle_hours_before_escalation: int
    reopen_escalation_enabled: bool
    reopen_count_for_escalation: int

    # CSAT
    csat_enabled: bool
    csat_survey_trigger: CSATSurveyTrigger
    csat_delay_hours: int
    csat_reminder_enabled: bool
    csat_reminder_days: int
    csat_survey_expiry_days: int
    default_csat_survey_id: Optional[int]

    # Customer Portal
    portal_enabled: bool
    portal_ticket_creation_enabled: bool
    portal_show_ticket_history: bool
    portal_show_knowledge_base: bool
    portal_show_faq: bool
    portal_require_login: bool

    # Knowledge Base
    kb_enabled: bool
    kb_public_access: bool
    kb_suggest_articles_on_create: bool
    kb_track_article_helpfulness: bool

    # Notifications
    notification_channels: List[str]
    notification_events: Dict[str, bool]
    notify_assigned_agent: bool
    notify_team_on_unassigned: bool
    notify_customer_on_status_change: bool
    notify_customer_on_reply: bool

    # Queue Management
    unassigned_warning_minutes: int
    overdue_highlight_enabled: bool
    queue_refresh_seconds: int

    # Integrations
    email_to_ticket_enabled: bool
    email_reply_to_address: Optional[str]
    sync_to_erpnext: bool
    sync_to_splynx: bool
    sync_to_chatwoot: bool

    # Data Retention
    archive_closed_tickets_days: int
    delete_archived_tickets_days: int

    # Display
    ticket_id_prefix: str
    ticket_id_min_digits: int
    date_format: str
    time_format: str

    model_config = ConfigDict(from_attributes=True)


class SupportSettingsUpdate(BaseModel):
    # Business Hours
    working_hours_type: Optional[WorkingHoursType] = None
    timezone: Optional[str] = None
    weekly_schedule: Optional[Dict[str, Any]] = None
    holiday_calendar_id: Optional[int] = None

    # SLA Defaults
    default_sla_policy_id: Optional[int] = None
    sla_warning_threshold_percent: Optional[int] = Field(None, ge=1, le=100)
    sla_include_holidays: Optional[bool] = None
    sla_include_weekends: Optional[bool] = None
    default_first_response_hours: Optional[Decimal] = Field(None, ge=0)
    default_resolution_hours: Optional[Decimal] = Field(None, ge=0)

    # Ticket Routing
    default_routing_strategy: Optional[DefaultRoutingStrategy] = None
    default_team_id: Optional[int] = None
    fallback_team_id: Optional[int] = None
    auto_assign_enabled: Optional[bool] = None
    max_tickets_per_agent: Optional[int] = Field(None, ge=1)
    rebalance_threshold_percent: Optional[int] = Field(None, ge=1, le=100)

    # Ticket Defaults
    default_priority: Optional[TicketPriorityDefault] = None
    default_ticket_type: Optional[str] = None
    allow_customer_priority_selection: Optional[bool] = None
    allow_customer_team_selection: Optional[bool] = None

    # Auto-Close
    auto_close_enabled: Optional[bool] = None
    auto_close_resolved_days: Optional[int] = Field(None, ge=1)
    auto_close_action: Optional[TicketAutoCloseAction] = None
    auto_close_notify_customer: Optional[bool] = None
    allow_customer_reopen: Optional[bool] = None
    reopen_window_days: Optional[int] = Field(None, ge=0)
    max_reopens_allowed: Optional[int] = Field(None, ge=0)

    # Escalation
    escalation_enabled: Optional[bool] = None
    default_escalation_team_id: Optional[int] = None
    escalation_notify_manager: Optional[bool] = None
    idle_escalation_enabled: Optional[bool] = None
    idle_hours_before_escalation: Optional[int] = Field(None, ge=1)
    reopen_escalation_enabled: Optional[bool] = None
    reopen_count_for_escalation: Optional[int] = Field(None, ge=1)

    # CSAT
    csat_enabled: Optional[bool] = None
    csat_survey_trigger: Optional[CSATSurveyTrigger] = None
    csat_delay_hours: Optional[int] = Field(None, ge=0)
    csat_reminder_enabled: Optional[bool] = None
    csat_reminder_days: Optional[int] = Field(None, ge=1)
    csat_survey_expiry_days: Optional[int] = Field(None, ge=1)
    default_csat_survey_id: Optional[int] = None

    # Customer Portal
    portal_enabled: Optional[bool] = None
    portal_ticket_creation_enabled: Optional[bool] = None
    portal_show_ticket_history: Optional[bool] = None
    portal_show_knowledge_base: Optional[bool] = None
    portal_show_faq: Optional[bool] = None
    portal_require_login: Optional[bool] = None

    # Knowledge Base
    kb_enabled: Optional[bool] = None
    kb_public_access: Optional[bool] = None
    kb_suggest_articles_on_create: Optional[bool] = None
    kb_track_article_helpfulness: Optional[bool] = None

    # Notifications
    notification_channels: Optional[List[str]] = None
    notification_events: Optional[Dict[str, bool]] = None
    notify_assigned_agent: Optional[bool] = None
    notify_team_on_unassigned: Optional[bool] = None
    notify_customer_on_status_change: Optional[bool] = None
    notify_customer_on_reply: Optional[bool] = None

    # Queue Management
    unassigned_warning_minutes: Optional[int] = Field(None, ge=1)
    overdue_highlight_enabled: Optional[bool] = None
    queue_refresh_seconds: Optional[int] = Field(None, ge=10)

    # Integrations
    email_to_ticket_enabled: Optional[bool] = None
    email_reply_to_address: Optional[str] = None
    sync_to_erpnext: Optional[bool] = None
    sync_to_splynx: Optional[bool] = None
    sync_to_chatwoot: Optional[bool] = None

    # Data Retention
    archive_closed_tickets_days: Optional[int] = Field(None, ge=0)
    delete_archived_tickets_days: Optional[int] = Field(None, ge=0)

    # Display
    ticket_id_prefix: Optional[str] = Field(None, max_length=10)
    ticket_id_min_digits: Optional[int] = Field(None, ge=1, le=10)
    date_format: Optional[str] = None
    time_format: Optional[str] = None


# Escalation Policy Schemas
class EscalationLevelCreate(BaseModel):
    level: int = Field(..., ge=1)
    trigger: str = "SLA_BREACH"
    trigger_hours: int = Field(0, ge=0)
    escalate_to_team_id: Optional[int] = None
    escalate_to_user_id: Optional[int] = None
    notify_current_assignee: bool = True
    notify_team_lead: bool = True
    reassign_ticket: bool = False
    change_priority: bool = False
    new_priority: Optional[str] = None
    notification_template: Optional[str] = None


class EscalationLevelResponse(BaseModel):
    id: int
    level: int
    trigger: str
    trigger_hours: int
    escalate_to_team_id: Optional[int]
    escalate_to_user_id: Optional[int]
    notify_current_assignee: bool
    notify_team_lead: bool
    reassign_ticket: bool
    change_priority: bool
    new_priority: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class EscalationPolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    conditions: List[dict] = []
    priority: int = Field(100, ge=1)
    levels: List[EscalationLevelCreate] = []


class EscalationPolicyResponse(BaseModel):
    id: int
    company: Optional[str]
    name: str
    description: Optional[str]
    conditions: List[dict]
    priority: int
    is_active: bool
    levels: List[EscalationLevelResponse]

    model_config = ConfigDict(from_attributes=True)


# Support Queue Schemas
class SupportQueueCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    filters: List[dict] = []
    sort_by: str = "created_at"
    sort_direction: str = "DESC"
    is_public: bool = True
    display_order: int = 100
    icon: Optional[str] = None
    color: Optional[str] = None


class SupportQueueResponse(BaseModel):
    id: int
    company: Optional[str]
    name: str
    description: Optional[str]
    queue_type: str
    filters: List[dict]
    sort_by: str
    sort_direction: str
    is_public: bool
    owner_id: Optional[int]
    display_order: int
    icon: Optional[str]
    color: Optional[str]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# Ticket Field Config Schemas
class TicketFieldConfigCreate(BaseModel):
    field_name: str = Field(..., min_length=1, max_length=100)
    field_key: str = Field(..., min_length=1, max_length=50)
    field_type: str  # TEXT, NUMBER, DROPDOWN, etc.
    options: Optional[List[dict]] = None
    is_required: bool = False
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    validation_regex: Optional[str] = None
    default_value: Optional[str] = None
    display_order: int = 100
    show_in_list: bool = False
    show_in_create_form: bool = True
    show_in_customer_portal: bool = False
    applies_to_types: Optional[List[str]] = None


class TicketFieldConfigResponse(BaseModel):
    id: int
    company: Optional[str]
    field_name: str
    field_key: str
    field_type: str
    options: Optional[List[dict]]
    is_required: bool
    min_length: Optional[int]
    max_length: Optional[int]
    validation_regex: Optional[str]
    default_value: Optional[str]
    display_order: int
    show_in_list: bool
    show_in_create_form: bool
    show_in_customer_portal: bool
    applies_to_types: Optional[List[str]]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# Email Template Schemas
class EmailTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    template_type: str
    subject: str
    body_html: str
    body_text: Optional[str] = None


class EmailTemplateResponse(BaseModel):
    id: int
    company: Optional[str]
    name: str
    template_type: str
    subject: str
    body_html: str
    body_text: Optional[str]
    supported_placeholders: List[str]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# SUPPORT SETTINGS ENDPOINTS
# =============================================================================

@router.get("", response_model=SupportSettingsResponse, dependencies=[Depends(Require("support:read"))])
def get_support_settings(
    company: Optional[str] = Query(None, description="Company name (null for global settings)"),
    db: Session = Depends(get_db)
):
    """Get support settings for company or global defaults"""
    settings = db.query(SupportSettings).filter(SupportSettings.company == company).first()

    if not settings:
        # Return global settings if company-specific not found
        settings = db.query(SupportSettings).filter(SupportSettings.company.is_(None)).first()

    if not settings:
        raise HTTPException(status_code=404, detail="Support settings not found. Run seed-defaults first.")

    return settings


@router.put("", response_model=SupportSettingsResponse, dependencies=[Depends(Require("support:admin"))])
def update_support_settings(
    data: SupportSettingsUpdate,
    company: Optional[str] = Query(None, description="Company name (null for global settings)"),
    db: Session = Depends(get_db)
):
    """Update support settings"""
    settings = db.query(SupportSettings).filter(SupportSettings.company == company).first()

    if not settings:
        raise HTTPException(status_code=404, detail="Support settings not found")

    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    db.commit()
    db.refresh(settings)
    return settings


@router.post("/seed-defaults", dependencies=[Depends(Require("support:admin"))])
def seed_support_defaults(db: Session = Depends(get_db)):
    """Seed default support settings if not exists"""
    existing = db.query(SupportSettings).filter(SupportSettings.company.is_(None)).first()
    if existing:
        return {"message": "Default support settings already exist", "id": existing.id}

    settings = SupportSettings(company=None)
    db.add(settings)
    db.commit()
    db.refresh(settings)

    # Create default system queues
    default_queues = [
        SupportQueue(
            company=None,
            name="Unassigned",
            description="Tickets awaiting assignment",
            queue_type="SYSTEM",
            filters=[{"field": "assignee_id", "operator": "is_empty", "value": None}],
            display_order=1,
            icon="inbox"
        ),
        SupportQueue(
            company=None,
            name="My Tickets",
            description="Tickets assigned to current user",
            queue_type="SYSTEM",
            filters=[{"field": "assignee_id", "operator": "equals", "value": "{{current_user}}"}],
            display_order=2,
            icon="user"
        ),
        SupportQueue(
            company=None,
            name="Overdue",
            description="SLA breached tickets",
            queue_type="SYSTEM",
            filters=[{"field": "sla_breached", "operator": "equals", "value": True}],
            display_order=3,
            icon="alert-triangle",
            color="#EF4444"
        ),
        SupportQueue(
            company=None,
            name="High Priority",
            description="High and urgent priority tickets",
            queue_type="SYSTEM",
            filters=[{"field": "priority", "operator": "in", "value": ["HIGH", "URGENT"]}],
            display_order=4,
            icon="flag",
            color="#F59E0B"
        ),
    ]
    for queue in default_queues:
        db.add(queue)

    db.commit()

    return {"message": "Default support settings and queues created", "id": settings.id}


# =============================================================================
# ESCALATION POLICY ENDPOINTS
# =============================================================================

@router.get("/escalation-policies", response_model=List[EscalationPolicyResponse], dependencies=[Depends(Require("support:read"))])
def list_escalation_policies(
    company: Optional[str] = None,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """List escalation policies"""
    query = db.query(EscalationPolicy)

    if company is not None:
        query = query.filter(EscalationPolicy.company == company)
    if is_active is not None:
        query = query.filter(EscalationPolicy.is_active == is_active)

    return query.order_by(EscalationPolicy.priority).all()


@router.post("/escalation-policies", response_model=EscalationPolicyResponse, dependencies=[Depends(Require("support:admin"))])
def create_escalation_policy(
    data: EscalationPolicyCreate,
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Create an escalation policy"""
    policy = EscalationPolicy(
        company=company,
        name=data.name,
        description=data.description,
        conditions=data.conditions,
        priority=data.priority
    )
    db.add(policy)
    db.flush()

    # Add levels
    for level_data in data.levels:
        level = EscalationLevel(
            policy_id=policy.id,
            level=level_data.level,
            trigger=EscalationTrigger(level_data.trigger),
            trigger_hours=level_data.trigger_hours,
            escalate_to_team_id=level_data.escalate_to_team_id,
            escalate_to_user_id=level_data.escalate_to_user_id,
            notify_current_assignee=level_data.notify_current_assignee,
            notify_team_lead=level_data.notify_team_lead,
            reassign_ticket=level_data.reassign_ticket,
            change_priority=level_data.change_priority,
            new_priority=level_data.new_priority,
            notification_template=level_data.notification_template
        )
        db.add(level)

    db.commit()
    db.refresh(policy)
    return policy


@router.get("/escalation-policies/{policy_id}", response_model=EscalationPolicyResponse, dependencies=[Depends(Require("support:read"))])
def get_escalation_policy(policy_id: int, db: Session = Depends(get_db)):
    """Get a specific escalation policy"""
    policy = db.query(EscalationPolicy).filter(EscalationPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Escalation policy not found")
    return policy


@router.put("/escalation-policies/{policy_id}", response_model=EscalationPolicyResponse, dependencies=[Depends(Require("support:admin"))])
def update_escalation_policy(policy_id: int, data: EscalationPolicyCreate, db: Session = Depends(get_db)):
    """Update an escalation policy"""
    policy = db.query(EscalationPolicy).filter(EscalationPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Escalation policy not found")

    _apply_updates(
        policy,
        {
            "name": data.name,
            "description": data.description,
            "conditions": data.conditions,
            "priority": data.priority,
        },
    )

    # Delete existing levels and recreate
    db.query(EscalationLevel).filter(EscalationLevel.policy_id == policy_id).delete()

    for level_data in data.levels:
        level = EscalationLevel(
            policy_id=policy.id,
            level=level_data.level,
            trigger=EscalationTrigger(level_data.trigger),
            trigger_hours=level_data.trigger_hours,
            escalate_to_team_id=level_data.escalate_to_team_id,
            escalate_to_user_id=level_data.escalate_to_user_id,
            notify_current_assignee=level_data.notify_current_assignee,
            notify_team_lead=level_data.notify_team_lead,
            reassign_ticket=level_data.reassign_ticket,
            change_priority=level_data.change_priority,
            new_priority=level_data.new_priority,
            notification_template=level_data.notification_template
        )
        db.add(level)

    db.commit()
    db.refresh(policy)
    return policy


@router.delete("/escalation-policies/{policy_id}", dependencies=[Depends(Require("support:admin"))])
def delete_escalation_policy(policy_id: int, db: Session = Depends(get_db)):
    """Deactivate an escalation policy"""
    policy = db.query(EscalationPolicy).filter(EscalationPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Escalation policy not found")

    _apply_updates(policy, {"is_active": False})
    db.commit()
    return {"message": "Escalation policy deactivated"}


# =============================================================================
# SUPPORT QUEUE ENDPOINTS
# =============================================================================

@router.get("/queues", response_model=List[SupportQueueResponse], dependencies=[Depends(Require("support:read"))])
def list_support_queues(
    company: Optional[str] = None,
    is_active: bool = True,
    include_system: bool = True,
    db: Session = Depends(get_db)
):
    """List support queues"""
    query = db.query(SupportQueue)

    if company is not None:
        query = query.filter(SupportQueue.company == company)
    else:
        query = query.filter(SupportQueue.company.is_(None))

    if is_active is not None:
        query = query.filter(SupportQueue.is_active == is_active)
    if not include_system:
        query = query.filter(SupportQueue.queue_type != "SYSTEM")

    return query.order_by(SupportQueue.display_order).all()


@router.post("/queues", response_model=SupportQueueResponse, dependencies=[Depends(Require("support:write"))])
def create_support_queue(
    data: SupportQueueCreate,
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Create a custom support queue"""
    queue = SupportQueue(
        company=company,
        name=data.name,
        description=data.description,
        queue_type="CUSTOM",
        filters=data.filters,
        sort_by=data.sort_by,
        sort_direction=data.sort_direction,
        is_public=data.is_public,
        display_order=data.display_order,
        icon=data.icon,
        color=data.color
    )
    db.add(queue)
    db.commit()
    db.refresh(queue)
    return queue


@router.put("/queues/{queue_id}", response_model=SupportQueueResponse, dependencies=[Depends(Require("support:write"))])
def update_support_queue(queue_id: int, data: SupportQueueCreate, db: Session = Depends(get_db)):
    """Update a support queue"""
    queue = db.query(SupportQueue).filter(SupportQueue.id == queue_id).first()
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    if queue.queue_type == "SYSTEM":
        raise HTTPException(status_code=400, detail="Cannot modify system queues")

    _apply_updates(
        queue,
        {
            "name": data.name,
            "description": data.description,
            "filters": data.filters,
            "sort_by": data.sort_by,
            "sort_direction": data.sort_direction,
            "is_public": data.is_public,
            "display_order": data.display_order,
            "icon": data.icon,
            "color": data.color,
        },
    )

    db.commit()
    db.refresh(queue)
    return queue


@router.delete("/queues/{queue_id}", dependencies=[Depends(Require("support:write"))])
def delete_support_queue(queue_id: int, db: Session = Depends(get_db)):
    """Deactivate a support queue"""
    queue = db.query(SupportQueue).filter(SupportQueue.id == queue_id).first()
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    if queue.queue_type == "SYSTEM":
        raise HTTPException(status_code=400, detail="Cannot delete system queues")

    _apply_updates(queue, {"is_active": False})
    db.commit()
    return {"message": "Queue deactivated"}


# =============================================================================
# TICKET FIELD CONFIG ENDPOINTS
# =============================================================================

@router.get("/ticket-fields", response_model=List[TicketFieldConfigResponse], dependencies=[Depends(Require("support:read"))])
def list_ticket_fields(
    company: Optional[str] = None,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """List custom ticket field configurations"""
    query = db.query(TicketFieldConfig)

    if company is not None:
        query = query.filter(TicketFieldConfig.company == company)
    if is_active is not None:
        query = query.filter(TicketFieldConfig.is_active == is_active)

    return query.order_by(TicketFieldConfig.display_order).all()


@router.post("/ticket-fields", response_model=TicketFieldConfigResponse, dependencies=[Depends(Require("support:admin"))])
def create_ticket_field(
    data: TicketFieldConfigCreate,
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Create a custom ticket field"""
    # Check for duplicate field_key
    existing = db.query(TicketFieldConfig).filter(
        TicketFieldConfig.company == company,
        TicketFieldConfig.field_key == data.field_key
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Field key already exists")

    field = TicketFieldConfig(
        company=company,
        field_name=data.field_name,
        field_key=data.field_key,
        field_type=data.field_type,
        options=data.options,
        is_required=data.is_required,
        min_length=data.min_length,
        max_length=data.max_length,
        validation_regex=data.validation_regex,
        default_value=data.default_value,
        display_order=data.display_order,
        show_in_list=data.show_in_list,
        show_in_create_form=data.show_in_create_form,
        show_in_customer_portal=data.show_in_customer_portal,
        applies_to_types=data.applies_to_types
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


@router.put("/ticket-fields/{field_id}", response_model=TicketFieldConfigResponse, dependencies=[Depends(Require("support:admin"))])
def update_ticket_field(field_id: int, data: TicketFieldConfigCreate, db: Session = Depends(get_db)):
    """Update a custom ticket field"""
    field = db.query(TicketFieldConfig).filter(TicketFieldConfig.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    _apply_updates(
        field,
        {
            "field_name": data.field_name,
            "field_type": data.field_type,
            "options": data.options,
            "is_required": data.is_required,
            "min_length": data.min_length,
            "max_length": data.max_length,
            "validation_regex": data.validation_regex,
            "default_value": data.default_value,
            "display_order": data.display_order,
            "show_in_list": data.show_in_list,
            "show_in_create_form": data.show_in_create_form,
            "show_in_customer_portal": data.show_in_customer_portal,
            "applies_to_types": data.applies_to_types,
        },
    )

    db.commit()
    db.refresh(field)
    return field


@router.delete("/ticket-fields/{field_id}", dependencies=[Depends(Require("support:admin"))])
def delete_ticket_field(field_id: int, db: Session = Depends(get_db)):
    """Deactivate a custom ticket field"""
    field = db.query(TicketFieldConfig).filter(TicketFieldConfig.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    _apply_updates(field, {"is_active": False})
    db.commit()
    return {"message": "Field deactivated"}


# =============================================================================
# EMAIL TEMPLATE ENDPOINTS
# =============================================================================

@router.get("/email-templates", response_model=List[EmailTemplateResponse], dependencies=[Depends(Require("support:read"))])
def list_email_templates(
    company: Optional[str] = None,
    template_type: Optional[str] = None,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """List email templates"""
    query = db.query(SupportEmailTemplate)

    if company is not None:
        query = query.filter(SupportEmailTemplate.company == company)
    if template_type is not None:
        query = query.filter(SupportEmailTemplate.template_type == template_type)
    if is_active is not None:
        query = query.filter(SupportEmailTemplate.is_active == is_active)

    return query.order_by(SupportEmailTemplate.template_type).all()


@router.post("/email-templates", response_model=EmailTemplateResponse, dependencies=[Depends(Require("support:admin"))])
def create_email_template(
    data: EmailTemplateCreate,
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Create an email template"""
    template = SupportEmailTemplate(
        company=company,
        name=data.name,
        template_type=data.template_type,
        subject=data.subject,
        body_html=data.body_html,
        body_text=data.body_text
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.put("/email-templates/{template_id}", response_model=EmailTemplateResponse, dependencies=[Depends(Require("support:admin"))])
def update_email_template(template_id: int, data: EmailTemplateCreate, db: Session = Depends(get_db)):
    """Update an email template"""
    template = db.query(SupportEmailTemplate).filter(SupportEmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    _apply_updates(
        template,
        {
            "name": data.name,
            "template_type": data.template_type,
            "subject": data.subject,
            "body_html": data.body_html,
            "body_text": data.body_text,
        },
    )

    db.commit()
    db.refresh(template)
    return template


@router.delete("/email-templates/{template_id}", dependencies=[Depends(Require("support:admin"))])
def delete_email_template(template_id: int, db: Session = Depends(get_db)):
    """Deactivate an email template"""
    template = db.query(SupportEmailTemplate).filter(SupportEmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    _apply_updates(template, {"is_active": False})
    db.commit()
    return {"message": "Template deactivated"}
