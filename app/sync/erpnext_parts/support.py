"""Support sync functions for ERPNext.

This module handles syncing of support-related entities:
- HD Tickets (Help Desk)
- Projects
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from app.models.customer import Customer
from app.models.employee import Employee
from app.models.project import Project, ProjectPriority, ProjectStatus
from app.models.ticket import Ticket, TicketPriority, TicketSource, TicketStatus

if TYPE_CHECKING:
    from app.sync.erpnext import ERPNextSync

logger = structlog.get_logger()


async def sync_hd_tickets(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync HD Tickets (Help Desk) from ERPNext with full FK relationships."""
    sync_client.start_sync("hd_tickets", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("hd_tickets", full_sync)

        tickets = await sync_client._fetch_all_doctype(
            client,
            "HD Ticket",
            fields=["*"],
            filters=filters,
        )

        # Pre-fetch customers by email and erpnext_id for linking
        customers_by_email = {
            c.email.lower(): c.id
            for c in sync_client.db.query(Customer).filter(Customer.email.isnot(None)).all()
            if c.email
        }
        customers_by_erpnext_id = {
            c.erpnext_id: c.id
            for c in sync_client.db.query(Customer).filter(Customer.erpnext_id.isnot(None)).all()
        }

        # Pre-fetch employees by email for linking
        employees_by_email = {
            e.email.lower(): e.id
            for e in sync_client.db.query(Employee).filter(Employee.email.isnot(None)).all()
            if e.email
        }

        # Pre-fetch projects by erpnext_id for linking
        projects_by_erpnext_id = {
            p.erpnext_id: p.id
            for p in sync_client.db.query(Project).filter(Project.erpnext_id.isnot(None)).all()
        }

        batch_size = 500
        for i, ticket_data in enumerate(tickets, 1):
            erpnext_id = str(ticket_data.get("name"))
            existing = sync_client.db.query(Ticket).filter(
                Ticket.erpnext_id == erpnext_id
            ).first()

            # Map status
            status_str = (ticket_data.get("custom_ticket_status") or ticket_data.get("status", "") or "").lower()
            status_map = {
                "open": TicketStatus.OPEN,
                "replied": TicketStatus.REPLIED,
                "resolved": TicketStatus.RESOLVED,
                "closed": TicketStatus.CLOSED,
                "on hold": TicketStatus.ON_HOLD,
            }
            status = status_map.get(status_str, TicketStatus.OPEN)

            # Map priority
            priority_str = (ticket_data.get("priority", "") or "").lower()
            priority_map = {
                "low": TicketPriority.LOW,
                "medium": TicketPriority.MEDIUM,
                "high": TicketPriority.HIGH,
                "urgent": TicketPriority.URGENT,
            }
            priority = priority_map.get(priority_str, TicketPriority.MEDIUM)

            # Extract data
            customer_email = ticket_data.get("custom_email")
            customer_phone = ticket_data.get("custom_phone")
            customer_name = ticket_data.get("custom_customer_name")
            region = ticket_data.get("custom_region")
            base_station = ticket_data.get("custom_base_station")
            raised_by = ticket_data.get("raised_by")
            owner_email = ticket_data.get("owner")
            erpnext_customer = ticket_data.get("customer")
            erpnext_project = ticket_data.get("project")
            resolution_team = ticket_data.get("custom_resolution_team")
            agent_email = ticket_data.get("agent")

            # Link to customer
            customer_id = None
            if erpnext_customer:
                customer_id = customers_by_erpnext_id.get(erpnext_customer)
            if not customer_id and customer_email:
                customer_id = customers_by_email.get(customer_email.lower())

            # Link to employee
            employee_id = None
            if raised_by:
                employee_id = employees_by_email.get(raised_by.lower())

            # Link to assigned agent
            assigned_employee_id = None
            if agent_email:
                assigned_employee_id = employees_by_email.get(agent_email.lower())

            # Link to project
            project_id = None
            if erpnext_project:
                project_id = projects_by_erpnext_id.get(erpnext_project)

            if existing:
                existing.subject = ticket_data.get("subject")
                existing.description = ticket_data.get("description")
                existing.ticket_type = ticket_data.get("ticket_type")
                existing.issue_type = ticket_data.get("ticket_type")
                existing.status = status
                existing.priority = priority

                existing.customer_id = customer_id
                existing.employee_id = employee_id
                existing.assigned_employee_id = assigned_employee_id
                existing.project_id = project_id
                existing.erpnext_customer = erpnext_customer
                existing.erpnext_project = erpnext_project

                existing.raised_by = raised_by
                existing.owner_email = owner_email
                existing.assigned_to = agent_email
                existing.resolution_team = resolution_team
                existing.company = ticket_data.get("company")

                existing.customer_email = customer_email
                existing.customer_phone = customer_phone
                existing.customer_name = customer_name

                existing.region = region
                existing.base_station = base_station

                existing.agreement_status = ticket_data.get("agreement_status")
                existing.resolution = ticket_data.get("resolution")
                existing.resolution_details = ticket_data.get("resolution_details")
                existing.feedback_rating = ticket_data.get("feedback_rating")
                existing.feedback_text = ticket_data.get("feedback_text")

                existing.last_synced_at = datetime.utcnow()

                date_fields = [
                    ("opening_date", "opening_date"),
                    ("resolution_date", "resolution_date"),
                    ("response_by", "response_by"),
                    ("resolution_by", "resolution_by"),
                    ("first_responded_on", "first_responded_on"),
                ]
                for model_field, data_field in date_fields:
                    if ticket_data.get(data_field):
                        try:
                            setattr(existing, model_field, datetime.fromisoformat(str(ticket_data[data_field])))
                        except (ValueError, TypeError):
                            pass

                sync_client.increment_updated()
            else:
                ticket = Ticket(
                    erpnext_id=erpnext_id,
                    source=TicketSource.ERPNEXT,
                    ticket_number=f"HD-{erpnext_id}",
                    subject=ticket_data.get("subject"),
                    description=ticket_data.get("description"),
                    ticket_type=ticket_data.get("ticket_type"),
                    issue_type=ticket_data.get("ticket_type"),
                    status=status,
                    priority=priority,
                    customer_id=customer_id,
                    employee_id=employee_id,
                    assigned_employee_id=assigned_employee_id,
                    project_id=project_id,
                    erpnext_customer=erpnext_customer,
                    erpnext_project=erpnext_project,
                    raised_by=raised_by,
                    owner_email=owner_email,
                    assigned_to=agent_email,
                    resolution_team=resolution_team,
                    company=ticket_data.get("company"),
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                    customer_name=customer_name,
                    region=region,
                    base_station=base_station,
                    agreement_status=ticket_data.get("agreement_status"),
                    resolution=ticket_data.get("resolution"),
                    resolution_details=ticket_data.get("resolution_details"),
                    feedback_rating=ticket_data.get("feedback_rating"),
                    feedback_text=ticket_data.get("feedback_text"),
                )

                date_fields = [
                    ("opening_date", "opening_date"),
                    ("resolution_date", "resolution_date"),
                    ("response_by", "response_by"),
                    ("resolution_by", "resolution_by"),
                    ("first_responded_on", "first_responded_on"),
                ]
                for model_field, data_field in date_fields:
                    if ticket_data.get(data_field):
                        try:
                            setattr(ticket, model_field, datetime.fromisoformat(str(ticket_data[data_field])))
                        except (ValueError, TypeError):
                            pass

                if not ticket.opening_date:
                    ticket.opening_date = datetime.utcnow()

                sync_client.db.add(ticket)
                sync_client.increment_created()

            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("hd_tickets_batch_committed", processed=i, total=len(tickets))

        sync_client.db.commit()
        sync_client._update_sync_cursor("hd_tickets", tickets, len(tickets))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_projects(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync projects from ERPNext with full fields and FK relationships."""
    sync_client.start_sync("projects", "full" if full_sync else "incremental")

    try:
        projects = await sync_client._fetch_all_doctype(
            client,
            "Project",
            fields=["*"],
        )

        # Pre-fetch customers
        customers_by_erpnext_id = {
            c.erpnext_id: c.id
            for c in sync_client.db.query(Customer).filter(Customer.erpnext_id.isnot(None)).all()
        }

        # Pre-fetch employees by email for project manager FK
        employees_by_email = {
            e.email: e.id
            for e in sync_client.db.query(Employee).filter(Employee.email.isnot(None)).all()
        }

        # Helper for Decimal conversion
        def to_decimal(val: Any) -> Decimal:
            return Decimal(str(val or 0))

        batch_size = 500
        for i, proj_data in enumerate(projects, 1):
            erpnext_id = proj_data.get("name")
            existing = sync_client.db.query(Project).filter(
                Project.erpnext_id == erpnext_id
            ).first()

            # Map status
            status_str = (proj_data.get("status", "") or "").lower()
            status_map = {
                "open": ProjectStatus.OPEN,
                "completed": ProjectStatus.COMPLETED,
                "cancelled": ProjectStatus.CANCELLED,
                "on hold": ProjectStatus.ON_HOLD,
            }
            status = status_map.get(status_str, ProjectStatus.OPEN)

            # Map priority
            priority_str = (proj_data.get("priority", "") or "").lower()
            priority_map = {
                "low": ProjectPriority.LOW,
                "medium": ProjectPriority.MEDIUM,
                "high": ProjectPriority.HIGH,
            }
            priority = priority_map.get(priority_str, ProjectPriority.MEDIUM)

            # Link to customer
            erpnext_customer = proj_data.get("customer")
            customer_id = customers_by_erpnext_id.get(erpnext_customer) if erpnext_customer else None

            # Link to project manager
            project_manager_email = proj_data.get("project_manager") or proj_data.get("owner")
            project_manager_id = employees_by_email.get(project_manager_email) if project_manager_email else None

            if existing:
                existing.project_name = proj_data.get("project_name", "")
                existing.project_type = proj_data.get("project_type")
                existing.status = status
                existing.priority = priority
                existing.department = proj_data.get("department")
                existing.company = proj_data.get("company")
                existing.cost_center = proj_data.get("cost_center")

                existing.customer_id = customer_id
                existing.erpnext_customer = erpnext_customer
                existing.erpnext_sales_order = proj_data.get("sales_order")
                existing.project_manager_id = project_manager_id

                existing.percent_complete = to_decimal(proj_data.get("percent_complete"))
                existing.percent_complete_method = proj_data.get("percent_complete_method")
                existing.is_active = proj_data.get("is_active", "Yes")

                existing.actual_time = to_decimal(proj_data.get("actual_time"))
                existing.total_consumed_material_cost = to_decimal(proj_data.get("total_consumed_material_cost"))

                existing.estimated_costing = to_decimal(proj_data.get("estimated_costing"))
                existing.total_costing_amount = to_decimal(proj_data.get("total_costing_amount"))
                existing.total_expense_claim = to_decimal(proj_data.get("total_expense_claim"))
                existing.total_purchase_cost = to_decimal(proj_data.get("total_purchase_cost"))

                existing.total_sales_amount = to_decimal(proj_data.get("total_sales_amount"))
                existing.total_billable_amount = to_decimal(proj_data.get("total_billable_amount"))
                existing.total_billed_amount = to_decimal(proj_data.get("total_billed_amount"))

                existing.gross_margin = to_decimal(proj_data.get("gross_margin"))
                existing.per_gross_margin = to_decimal(proj_data.get("per_gross_margin"))

                existing.collect_progress = proj_data.get("collect_progress", 0) == 1
                existing.frequency = proj_data.get("frequency")
                existing.message = proj_data.get("message")
                existing.notes = proj_data.get("notes")

                existing.last_synced_at = datetime.utcnow()

                date_fields = ["expected_start_date", "expected_end_date", "actual_start_date", "actual_end_date"]
                for date_field in date_fields:
                    if proj_data.get(date_field):
                        try:
                            setattr(existing, date_field, datetime.fromisoformat(proj_data[date_field]))
                        except (ValueError, TypeError):
                            pass

                for time_field in ["from_time", "to_time"]:
                    if proj_data.get(time_field):
                        try:
                            setattr(existing, time_field, datetime.fromisoformat(proj_data[time_field]))
                        except (ValueError, TypeError):
                            pass

                sync_client.increment_updated()
            else:
                project = Project(
                    erpnext_id=erpnext_id,
                    project_name=proj_data.get("project_name", ""),
                    project_type=proj_data.get("project_type"),
                    status=status,
                    priority=priority,
                    department=proj_data.get("department"),
                    company=proj_data.get("company"),
                    cost_center=proj_data.get("cost_center"),
                    customer_id=customer_id,
                    erpnext_customer=erpnext_customer,
                    erpnext_sales_order=proj_data.get("sales_order"),
                    project_manager_id=project_manager_id,
                    percent_complete=to_decimal(proj_data.get("percent_complete")),
                    percent_complete_method=proj_data.get("percent_complete_method"),
                    is_active=proj_data.get("is_active", "Yes"),
                    actual_time=to_decimal(proj_data.get("actual_time")),
                    total_consumed_material_cost=to_decimal(proj_data.get("total_consumed_material_cost")),
                    estimated_costing=to_decimal(proj_data.get("estimated_costing")),
                    total_costing_amount=to_decimal(proj_data.get("total_costing_amount")),
                    total_expense_claim=to_decimal(proj_data.get("total_expense_claim")),
                    total_purchase_cost=to_decimal(proj_data.get("total_purchase_cost")),
                    total_sales_amount=to_decimal(proj_data.get("total_sales_amount")),
                    total_billable_amount=to_decimal(proj_data.get("total_billable_amount")),
                    total_billed_amount=to_decimal(proj_data.get("total_billed_amount")),
                    gross_margin=to_decimal(proj_data.get("gross_margin")),
                    per_gross_margin=to_decimal(proj_data.get("per_gross_margin")),
                    collect_progress=proj_data.get("collect_progress", 0) == 1,
                    frequency=proj_data.get("frequency"),
                    message=proj_data.get("message"),
                    notes=proj_data.get("notes"),
                )

                date_fields = ["expected_start_date", "expected_end_date", "actual_start_date", "actual_end_date"]
                for date_field in date_fields:
                    if proj_data.get(date_field):
                        try:
                            setattr(project, date_field, datetime.fromisoformat(proj_data[date_field]))
                        except (ValueError, TypeError):
                            pass

                for time_field in ["from_time", "to_time"]:
                    if proj_data.get(time_field):
                        try:
                            setattr(project, time_field, datetime.fromisoformat(proj_data[time_field]))
                        except (ValueError, TypeError):
                            pass

                sync_client.db.add(project)
                sync_client.increment_created()

            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("projects_batch_committed", processed=i, total=len(projects))

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
