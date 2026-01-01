"""
Shared dependencies for CRM routes.

This module contains common imports, helpers, and permission dependencies
used across all CRM route modules (contacts, leads, opportunities, activities).
"""
from __future__ import annotations

from typing import Optional, Any, List, Dict
from datetime import datetime, date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import joinedload, Session

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request, htmx_toast, htmx_close_modal, set_flash

# Models - Contacts
from app.models.contact import Contact, ContactType, ContactStatus, ContactCategory

# Models - Leads
from app.models.sales import ERPNextLead, ERPNextLeadStatus

# Models - Opportunities & Activities
from app.models.crm import Opportunity, OpportunityStatus, Activity, ActivityType, ActivityStatus

# Models - Related (for cross-module queries)
from app.models.customer import Customer, CustomerStatus, CustomerType
from app.models.employee import Employee

# Permission dependencies
RequireCRMRead = Depends(require_scope("crm:read"))
RequireCRMWrite = Depends(require_scope("crm:write"))

# Template environment
templates = get_template_env()


# =============================================================================
# COMMON HELPER FUNCTIONS
# =============================================================================

def _form_str(form: Any, key: str, default: str = "") -> str:
    """Extract string value from form data."""
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str, default: Optional[int] = None) -> Optional[int]:
    """Extract integer value from form data."""
    value = _form_str(form, key, "")
    if not value:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _form_date(form: Any, key: str) -> Optional[date]:
    """Extract date value from form data."""
    value = form.get(key)
    if isinstance(value, UploadFile) or not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def _form_decimal(form: Any, key: str, default=None):
    """Extract decimal value from form data."""
    from decimal import Decimal, InvalidOperation
    value = _form_str(form, key, "")
    if not value:
        return default
    try:
        return Decimal(value)
    except InvalidOperation:
        return default


# =============================================================================
# CONTACT ENUM OPTIONS
# =============================================================================

def get_contact_status_options():
    """Get contact status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in ContactStatus
    ]


def get_contact_type_options():
    """Get contact type options for select dropdown."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in ContactType
    ]


# =============================================================================
# DYNAMIC OPTIONS FROM DATABASE
# =============================================================================

def get_owner_options(db):
    """Get active employees for owner assignment dropdown."""
    employees = db.query(Employee).filter(
        Employee.is_deleted == False,
        Employee.status == "active"
    ).order_by(Employee.first_name).all()
    return [
        {"value": str(e.id), "label": f"{e.first_name} {e.last_name}".strip() or e.email}
        for e in employees
    ]


def get_customer_options(db):
    """Get customers for linking dropdown."""
    customers = db.query(Customer).filter(
        Customer.is_deleted == False
    ).order_by(Customer.customer_name).limit(100).all()
    return [
        {"value": str(c.id), "label": c.customer_name}
        for c in customers
    ]


# =============================================================================
# LEAD ENUM OPTIONS
# =============================================================================

def get_lead_status_options():
    """Get lead status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in ERPNextLeadStatus
    ]


def get_lead_source_options():
    """Get common lead source options."""
    return [
        {"value": "website", "label": "Website"},
        {"value": "referral", "label": "Referral"},
        {"value": "cold_call", "label": "Cold Call"},
        {"value": "advertisement", "label": "Advertisement"},
        {"value": "social_media", "label": "Social Media"},
        {"value": "trade_show", "label": "Trade Show"},
        {"value": "partner", "label": "Partner"},
        {"value": "other", "label": "Other"},
    ]


def get_territory_options():
    """Get common territory options."""
    return [
        {"value": "lagos", "label": "Lagos"},
        {"value": "abuja", "label": "Abuja"},
        {"value": "port_harcourt", "label": "Port Harcourt"},
        {"value": "kano", "label": "Kano"},
        {"value": "ibadan", "label": "Ibadan"},
        {"value": "nationwide", "label": "Nationwide"},
        {"value": "international", "label": "International"},
    ]


def get_industry_options():
    """Get common industry options."""
    return [
        {"value": "technology", "label": "Technology"},
        {"value": "finance", "label": "Finance"},
        {"value": "healthcare", "label": "Healthcare"},
        {"value": "manufacturing", "label": "Manufacturing"},
        {"value": "retail", "label": "Retail"},
        {"value": "real_estate", "label": "Real Estate"},
        {"value": "education", "label": "Education"},
        {"value": "hospitality", "label": "Hospitality"},
        {"value": "other", "label": "Other"},
    ]


# =============================================================================
# OPPORTUNITY ENUM OPTIONS
# =============================================================================

def get_opportunity_status_options():
    """Get opportunity status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in OpportunityStatus
    ]


# =============================================================================
# ACTIVITY ENUM OPTIONS
# =============================================================================

def get_activity_type_options():
    """Get activity type options for select dropdown."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in ActivityType
    ]


def get_activity_status_options():
    """Get activity status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in ActivityStatus
    ]


def get_priority_options():
    """Get priority options for activities."""
    return [
        {"value": "low", "label": "Low"},
        {"value": "medium", "label": "Medium"},
        {"value": "high", "label": "High"},
        {"value": "urgent", "label": "Urgent"},
    ]


# =============================================================================
# CRM WEB SERVICE
# =============================================================================

class CRMWebService:
    """
    Service class for CRM UI operations.

    Encapsulates all database operations for the CRM module,
    providing a clean interface for route handlers.
    """

    def __init__(self, db: Session, user_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id

    # =========================================================================
    # LEADS
    # =========================================================================

    def get_leads_summary(self) -> Dict[str, Any]:
        """Get lead summary statistics."""
        total = self.db.query(func.count(ERPNextLead.id)).scalar() or 0
        new_leads = self.db.query(func.count(ERPNextLead.id)).filter(
            ERPNextLead.status == ERPNextLeadStatus.LEAD
        ).scalar() or 0
        qualified = self.db.query(func.count(ERPNextLead.id)).filter(
            ERPNextLead.status == ERPNextLeadStatus.OPPORTUNITY
        ).scalar() or 0
        converted = self.db.query(func.count(ERPNextLead.id)).filter(
            ERPNextLead.converted == True
        ).scalar() or 0
        lost = self.db.query(func.count(ERPNextLead.id)).filter(
            ERPNextLead.status == ERPNextLeadStatus.DO_NOT_CONTACT
        ).scalar() or 0

        return {
            "total": total,
            "new": new_leads,
            "qualified": qualified,
            "converted": converted,
            "lost": lost,
        }

    def list_leads(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        territory: Optional[str] = None,
        converted: Optional[bool] = None,
        page: int = 1,
        per_page: int = 25,
        sort: str = "created_at",
        dir: str = "desc",
    ) -> Dict[str, Any]:
        """List leads with filtering, search, and pagination."""
        query = self.db.query(ERPNextLead)

        # Search
        if q:
            search_filter = or_(
                ERPNextLead.lead_name.ilike(f"%{q}%"),
                ERPNextLead.company_name.ilike(f"%{q}%"),
                ERPNextLead.email_id.ilike(f"%{q}%"),
            )
            query = query.filter(search_filter)

        # Filters
        if status:
            try:
                status_enum = ERPNextLeadStatus(status.lower())
                query = query.filter(ERPNextLead.status == status_enum)
            except ValueError:
                pass
        if source:
            query = query.filter(ERPNextLead.source == source)
        if territory:
            query = query.filter(ERPNextLead.territory == territory)
        if converted is not None:
            query = query.filter(ERPNextLead.converted == converted)

        # Count total
        total = query.count()

        # Sorting
        sort_column = getattr(ERPNextLead, sort, ERPNextLead.created_at)
        if dir == "desc":
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)

        # Pagination
        offset = (page - 1) * per_page
        items = query.offset(offset).limit(per_page).all()
        pages = (total + per_page - 1) // per_page

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    def get_lead(self, lead_id: int) -> Optional[ERPNextLead]:
        """Get a single lead by ID."""
        return self.db.query(ERPNextLead).filter(
            ERPNextLead.id == lead_id
        ).first()

    def create_lead(self, data: Dict[str, Any]) -> ERPNextLead:
        """Create a new lead."""
        data.setdefault("status", ERPNextLeadStatus.LEAD)
        data.setdefault("created_at", datetime.utcnow())
        data.setdefault("converted", False)

        lead = ERPNextLead(**data)
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)

        return lead

    def update_lead(self, lead_id: int, data: Dict[str, Any]) -> Optional[ERPNextLead]:
        """Update an existing lead."""
        lead = self.get_lead(lead_id)
        if not lead:
            return None

        data["updated_at"] = datetime.utcnow()

        for key, value in data.items():
            if hasattr(lead, key) and value is not None:
                if key == "status" and isinstance(value, str):
                    try:
                        value = ERPNextLeadStatus(value.lower())
                    except ValueError:
                        continue
                setattr(lead, key, value)

        self.db.commit()
        self.db.refresh(lead)

        return lead

    def qualify_lead(self, lead_id: int) -> Optional[ERPNextLead]:
        """Mark a lead as qualified."""
        lead = self.get_lead(lead_id)
        if not lead:
            return None

        lead.status = ERPNextLeadStatus.OPPORTUNITY
        lead.qualification_status = "qualified"
        lead.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(lead)

        return lead

    def disqualify_lead(self, lead_id: int, reason: Optional[str] = None) -> Optional[ERPNextLead]:
        """Mark a lead as disqualified."""
        lead = self.get_lead(lead_id)
        if not lead:
            return None

        lead.status = ERPNextLeadStatus.DO_NOT_CONTACT
        lead.qualification_status = "disqualified"
        if reason:
            lead.notes = f"{lead.notes or ''}\n\nDisqualification reason: {reason}".strip()
        lead.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(lead)

        return lead

    def convert_lead(
        self,
        lead_id: int,
        customer_name: Optional[str] = None,
        customer_type: str = "business",
        create_opportunity: bool = False,
        opportunity_name: Optional[str] = None,
        deal_value: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Convert a lead to a customer."""
        lead = self.get_lead(lead_id)
        if not lead:
            return {"success": False, "error": "Lead not found"}

        if lead.converted:
            return {"success": False, "error": "Lead already converted"}

        # Determine customer type
        cust_type = CustomerType.BUSINESS
        if customer_type == "residential":
            cust_type = CustomerType.RESIDENTIAL
        elif customer_type == "enterprise":
            cust_type = CustomerType.ENTERPRISE

        # Create customer
        customer = Customer(
            customer_name=customer_name or lead.company_name or lead.lead_name,
            email=lead.email_id,
            phone=lead.phone or lead.mobile_no,
            city=lead.city,
            state=lead.state,
            country=lead.country or "Nigeria",
            customer_type=cust_type,
            status=CustomerStatus.ACTIVE,
            notes=lead.notes,
            conversion_date=datetime.utcnow(),
        )
        self.db.add(customer)
        self.db.flush()

        # Create primary contact
        contact = Contact(
            name=lead.lead_name or "Primary Contact",
            contact_type=ContactType.PERSON,
            category=ContactCategory.BUSINESS if cust_type in (CustomerType.BUSINESS, CustomerType.ENTERPRISE) else ContactCategory.RESIDENTIAL,
            email=lead.email_id,
            phone=lead.phone or lead.mobile_no,
            is_primary_contact=True,
            legacy_customer_id=customer.id,
        )
        self.db.add(contact)

        # Optionally create opportunity
        opportunity_id = None
        if create_opportunity:
            opportunity = Opportunity(
                name=opportunity_name or f"Opportunity from {lead.lead_name}",
                customer_id=customer.id,
                lead_id=lead.id,
                deal_value=Decimal(str(deal_value or 0)),
                probability=20,
                source=lead.source,
                status=OpportunityStatus.OPEN,
            )
            opportunity.update_weighted_value()
            self.db.add(opportunity)
            self.db.flush()
            opportunity_id = opportunity.id

        # Mark lead as converted
        lead.converted = True
        lead.status = ERPNextLeadStatus.CONVERTED
        lead.updated_at = datetime.utcnow()

        self.db.commit()

        return {
            "success": True,
            "customer_id": customer.id,
            "contact_id": contact.id,
            "opportunity_id": opportunity_id,
            "message": f"Lead converted to customer: {customer.name}",
        }

    # =========================================================================
    # ACTIVITIES
    # =========================================================================

    def get_activities_summary(self) -> Dict[str, Any]:
        """Get activity summary statistics."""
        from datetime import timezone

        now = datetime.now(timezone.utc)
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = datetime.combine(date.today(), datetime.max.time())
        week_end = now + timedelta(days=7)

        total = self.db.query(func.count(Activity.id)).scalar() or 0

        # By type
        type_counts = self.db.query(
            Activity.activity_type, func.count(Activity.id)
        ).group_by(Activity.activity_type).all()
        by_type = {t.value if t else "unknown": c for t, c in type_counts}

        # By status
        status_counts = self.db.query(
            Activity.status, func.count(Activity.id)
        ).group_by(Activity.status).all()
        by_status = {s.value if s else "unknown": c for s, c in status_counts}

        # Overdue (scheduled in past, not completed)
        overdue = self.db.query(func.count(Activity.id)).filter(
            Activity.status == ActivityStatus.PLANNED,
            Activity.scheduled_at < now
        ).scalar() or 0

        # Today
        today_count = self.db.query(func.count(Activity.id)).filter(
            Activity.scheduled_at >= today_start,
            Activity.scheduled_at <= today_end
        ).scalar() or 0

        # Upcoming week
        upcoming = self.db.query(func.count(Activity.id)).filter(
            Activity.status == ActivityStatus.PLANNED,
            Activity.scheduled_at >= now,
            Activity.scheduled_at <= week_end
        ).scalar() or 0

        return {
            "total": total,
            "by_type": by_type,
            "by_status": by_status,
            "overdue": overdue,
            "today": today_count,
            "upcoming_week": upcoming,
        }

    def list_activities(
        self,
        q: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[str] = None,
        lead_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        opportunity_id: Optional[int] = None,
        owner_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        per_page: int = 25,
        sort: str = "scheduled_at",
        dir: str = "desc",
    ) -> Dict[str, Any]:
        """List activities with filtering, search, and pagination."""
        query = self.db.query(Activity).options(
            joinedload(Activity.lead),
            joinedload(Activity.customer),
            joinedload(Activity.opportunity),
        )

        # Search
        if q:
            search_filter = Activity.subject.ilike(f"%{q}%")
            query = query.filter(search_filter)

        # Filters
        if activity_type:
            try:
                type_enum = ActivityType(activity_type.lower())
                query = query.filter(Activity.activity_type == type_enum)
            except ValueError:
                pass
        if status:
            try:
                status_enum = ActivityStatus(status.lower())
                query = query.filter(Activity.status == status_enum)
            except ValueError:
                pass
        if lead_id:
            query = query.filter(Activity.lead_id == lead_id)
        if customer_id:
            query = query.filter(Activity.customer_id == customer_id)
        if opportunity_id:
            query = query.filter(Activity.opportunity_id == opportunity_id)
        if owner_id:
            query = query.filter(Activity.owner_id == owner_id)
        if start_date:
            query = query.filter(Activity.scheduled_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(Activity.scheduled_at <= datetime.combine(end_date, datetime.max.time()))

        # Count total
        total = query.count()

        # Sorting
        sort_map = {
            "scheduled_at": Activity.scheduled_at,
            "created_at": Activity.created_at,
            "updated_at": Activity.updated_at,
        }
        sort_column = sort_map.get(sort, Activity.scheduled_at)
        order_column: Any = sort_column
        if sort == "scheduled_at":
            order_column = (
                sort_column.desc().nullslast()
                if dir == "desc"
                else sort_column.asc().nullsfirst()
            )
        elif dir == "desc":
            order_column = sort_column.desc()
        query = query.order_by(order_column, Activity.created_at.desc())

        # Pagination
        offset = (page - 1) * per_page
        items = query.offset(offset).limit(per_page).all()
        pages = (total + per_page - 1) // per_page

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    def get_activity(self, activity_id: int) -> Optional[Activity]:
        """Get a single activity by ID."""
        return self.db.query(Activity).options(
            joinedload(Activity.lead),
            joinedload(Activity.customer),
            joinedload(Activity.opportunity),
        ).filter(Activity.id == activity_id).first()

    def create_activity(self, data: Dict[str, Any]) -> Activity:
        """Create a new activity."""
        # Convert type string to enum
        activity_type_str = data.pop("activity_type", "task")
        try:
            activity_type = ActivityType(activity_type_str.lower())
        except ValueError:
            activity_type = ActivityType.TASK

        data["activity_type"] = activity_type
        data.setdefault("status", ActivityStatus.PLANNED)
        data.setdefault("created_at", datetime.utcnow())
        data.setdefault("updated_at", datetime.utcnow())

        activity = Activity(**data)
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)

        return activity

    def update_activity(self, activity_id: int, data: Dict[str, Any]) -> Optional[Activity]:
        """Update an existing activity."""
        activity = self.db.query(Activity).filter(Activity.id == activity_id).first()
        if not activity:
            return None

        data["updated_at"] = datetime.utcnow()

        for key, value in data.items():
            if hasattr(activity, key) and value is not None:
                if key == "activity_type" and isinstance(value, str):
                    try:
                        value = ActivityType(value.lower())
                    except ValueError:
                        continue
                if key == "status" and isinstance(value, str):
                    try:
                        value = ActivityStatus(value.lower())
                    except ValueError:
                        continue
                setattr(activity, key, value)

        self.db.commit()
        self.db.refresh(activity)

        return activity

    def complete_activity(
        self,
        activity_id: int,
        outcome: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[Activity]:
        """Mark an activity as completed."""
        from datetime import timezone

        activity = self.db.query(Activity).filter(Activity.id == activity_id).first()
        if not activity:
            return None

        activity.status = ActivityStatus.COMPLETED
        activity.completed_at = datetime.now(timezone.utc)
        activity.updated_at = datetime.utcnow()

        if outcome and activity.activity_type == ActivityType.CALL:
            activity.call_outcome = outcome

        if notes:
            activity.description = f"{activity.description or ''}\n\nCompletion notes: {notes}".strip()

        self.db.commit()
        self.db.refresh(activity)

        return activity

    def cancel_activity(self, activity_id: int) -> Optional[Activity]:
        """Cancel an activity."""
        activity = self.db.query(Activity).filter(Activity.id == activity_id).first()
        if not activity:
            return None

        activity.status = ActivityStatus.CANCELLED
        activity.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(activity)

        return activity

    def delete_activity(self, activity_id: int) -> bool:
        """Delete an activity."""
        activity = self.db.query(Activity).filter(Activity.id == activity_id).first()
        if not activity:
            return False

        self.db.delete(activity)
        self.db.commit()

        return True

    def get_lead_options(self) -> List[Dict[str, Any]]:
        """Get leads for linking dropdown."""
        leads = self.db.query(ERPNextLead).filter(
            ERPNextLead.converted == False
        ).order_by(ERPNextLead.lead_name).limit(100).all()
        return [
            {"value": str(l.id), "label": l.lead_name}
            for l in leads
        ]

    def get_opportunity_options(self) -> List[Dict[str, Any]]:
        """Get opportunities for linking dropdown."""
        opps = self.db.query(Opportunity).filter(
            Opportunity.status.in_([OpportunityStatus.OPEN])
        ).order_by(Opportunity.name).limit(100).all()
        return [
            {"value": str(o.id), "label": o.name}
            for o in opps
        ]
