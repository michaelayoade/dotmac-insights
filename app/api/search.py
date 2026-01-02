from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Dict, Any

from app.database import get_db
from app.auth import Principal, get_current_principal
from app.models.contact import Contact
from app.models.customer import Customer
from app.models.ticket import Ticket, TicketStatus
from app.models.invoice import Invoice
from app.models.employee import Employee
from app.models.project import Project
from app.models.subscription import Subscription

router = APIRouter()


@router.get("/search")
async def global_search(
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Global search across multiple entity types."""
    results: List[Dict[str, Any]] = []
    search_term = f"%{q.lower()}%"
    per_type_limit = max(5, limit // 4)

    # Search Contacts
    if principal.has_scope("crm:read"):
        contacts = (
            db.query(Contact)
            .filter(
                Contact.tenant_id == principal.tenant_id,
                or_(
                    func.lower(Contact.first_name).like(search_term),
                    func.lower(Contact.last_name).like(search_term),
                    func.lower(Contact.email).like(search_term),
                    func.lower(Contact.phone).like(search_term),
                    func.lower(Contact.company).like(search_term),
                ),
            )
            .limit(per_type_limit)
            .all()
        )
        for c in contacts:
            name = f"{c.first_name or ''} {c.last_name or ''}".strip() or c.email
            results.append({
                "id": str(c.id),
                "type": "contact",
                "title": name,
                "subtitle": c.email or c.phone or "",
                "url": f"/crm/contacts/{c.id}",
                "status": c.status.value if c.status else None,
            })

    # Search Customers
    if principal.has_scope("customers:read"):
        customers = (
            db.query(Customer)
            .filter(
                Customer.tenant_id == principal.tenant_id,
                or_(
                    func.lower(Customer.name).like(search_term),
                    func.lower(Customer.email).like(search_term),
                    func.lower(Customer.account_number).like(search_term),
                ),
            )
            .limit(per_type_limit)
            .all()
        )
        for c in customers:
            results.append({
                "id": str(c.id),
                "type": "customer",
                "title": c.name,
                "subtitle": c.email or c.account_number or "",
                "url": f"/customers/{c.id}",
                "status": c.status.value if c.status else None,
            })

    # Search Tickets
    if principal.has_scope("support:read"):
        tickets = (
            db.query(Ticket)
            .filter(
                Ticket.tenant_id == principal.tenant_id,
                or_(
                    func.lower(Ticket.subject).like(search_term),
                    func.lower(Ticket.ticket_number).like(search_term),
                ),
            )
            .limit(per_type_limit)
            .all()
        )
        for t in tickets:
            results.append({
                "id": str(t.id),
                "type": "ticket",
                "title": t.subject,
                "subtitle": t.ticket_number or "",
                "url": f"/support/tickets/{t.id}",
                "status": t.status.value if t.status else None,
            })

    # Search Invoices
    if principal.has_scope("accounting:read"):
        invoices = (
            db.query(Invoice)
            .filter(
                Invoice.tenant_id == principal.tenant_id,
                or_(
                    func.lower(Invoice.invoice_number).like(search_term),
                    func.lower(Invoice.customer_name).like(search_term),
                ),
            )
            .limit(per_type_limit)
            .all()
        )
        for inv in invoices:
            results.append({
                "id": str(inv.id),
                "type": "invoice",
                "title": inv.invoice_number,
                "subtitle": inv.customer_name or "",
                "url": f"/invoices/{inv.id}",
                "status": inv.status.value if inv.status else None,
            })

    # Search Employees
    if principal.has_scope("hr:read"):
        employees = (
            db.query(Employee)
            .filter(
                Employee.tenant_id == principal.tenant_id,
                or_(
                    func.lower(Employee.first_name).like(search_term),
                    func.lower(Employee.last_name).like(search_term),
                    func.lower(Employee.email).like(search_term),
                    func.lower(Employee.employee_number).like(search_term),
                ),
            )
            .limit(per_type_limit)
            .all()
        )
        for e in employees:
            name = f"{e.first_name or ''} {e.last_name or ''}".strip()
            results.append({
                "id": str(e.id),
                "type": "employee",
                "title": name,
                "subtitle": e.employee_number or e.email or "",
                "url": f"/hr/employees/{e.id}",
                "status": e.employment_status.value if e.employment_status else None,
            })

    # Search Projects
    if principal.has_scope("projects:read"):
        projects = (
            db.query(Project)
            .filter(
                Project.tenant_id == principal.tenant_id,
                or_(
                    func.lower(Project.name).like(search_term),
                    func.lower(Project.project_code).like(search_term),
                ),
            )
            .limit(per_type_limit)
            .all()
        )
        for p in projects:
            results.append({
                "id": str(p.id),
                "type": "project",
                "title": p.name,
                "subtitle": p.project_code or "",
                "url": f"/projects/{p.id}",
                "status": p.status.value if p.status else None,
            })

    # Search Subscriptions
    if principal.has_scope("subscriptions:read"):
        subscriptions = (
            db.query(Subscription)
            .filter(
                Subscription.tenant_id == principal.tenant_id,
                or_(
                    func.lower(Subscription.subscription_id).like(search_term),
                    func.lower(Subscription.customer_name).like(search_term),
                ),
            )
            .limit(per_type_limit)
            .all()
        )
        for s in subscriptions:
            results.append({
                "id": str(s.id),
                "type": "subscription",
                "title": s.subscription_id,
                "subtitle": s.customer_name or "",
                "url": f"/subscriptions/{s.id}",
                "status": s.status.value if s.status else None,
            })

    return {"results": results[:limit], "query": q}
