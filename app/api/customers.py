from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Dict, Any, Optional
from datetime import datetime

from app.database import get_db
from app.models.customer import Customer, CustomerStatus, CustomerType, BillingType
from app.models.subscription import Subscription
from app.models.invoice import Invoice
from app.models.conversation import Conversation, ConversationStatus
from app.models.pop import Pop
from app.auth import Require

router = APIRouter()


@router.get("/", dependencies=[Depends(Require("explorer:read"))])
async def list_customers(
    status: Optional[str] = None,
    customer_type: Optional[str] = None,
    billing_type: Optional[str] = None,
    pop_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List customers with filtering and pagination."""
    query = db.query(Customer)

    if status:
        try:
            status_enum = CustomerStatus(status)
            query = query.filter(Customer.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if customer_type:
        try:
            type_enum = CustomerType(customer_type)
            query = query.filter(Customer.customer_type == type_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid customer_type: {customer_type}")

    if billing_type:
        try:
            billing_enum = BillingType(billing_type)
            query = query.filter(Customer.billing_type == billing_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid billing_type: {billing_type}")

    if pop_id:
        query = query.filter(Customer.pop_id == pop_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Customer.name.ilike(search_term),
                Customer.email.ilike(search_term),
                Customer.phone.ilike(search_term),
                Customer.account_number.ilike(search_term),
            )
        )

    total = query.count()
    customers = query.order_by(Customer.name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "status": c.status.value,
                "customer_type": c.customer_type.value,
                "billing_type": c.billing_type.value if c.billing_type else None,
                "pop_id": c.pop_id,
                "account_number": c.account_number,
                "signup_date": c.signup_date.isoformat() if c.signup_date else None,
                "tenure_days": c.tenure_days,
                "splynx_id": c.splynx_id,
                "erpnext_id": c.erpnext_id,
                "chatwoot_contact_id": c.chatwoot_contact_id,
            }
            for c in customers
        ],
    }


@router.get("/{customer_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_customer(customer_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get detailed customer information including related data."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get subscriptions
    subscriptions = db.query(Subscription).filter(Subscription.customer_id == customer_id).all()

    # Get recent invoices
    invoices = (
        db.query(Invoice)
        .filter(Invoice.customer_id == customer_id)
        .order_by(Invoice.invoice_date.desc())
        .limit(20)
        .all()
    )

    # Get conversations
    conversations = (
        db.query(Conversation)
        .filter(Conversation.customer_id == customer_id)
        .order_by(Conversation.created_at.desc())
        .limit(20)
        .all()
    )

    # Calculate metrics
    total_invoiced = sum(float(inv.total_amount or 0) for inv in invoices)
    total_paid = sum(float(inv.amount_paid or 0) for inv in invoices)
    outstanding = total_invoiced - total_paid

    open_tickets = len([c for c in conversations if c.status == ConversationStatus.OPEN])

    pop = None
    if customer.pop_id:
        pop_obj = db.query(Pop).filter(Pop.id == customer.pop_id).first()
        if pop_obj:
            pop = {"id": pop_obj.id, "name": pop_obj.name}

    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "phone_secondary": customer.phone_secondary,
        "address": customer.address,
        "city": customer.city,
        "state": customer.state,
        "status": customer.status.value,
        "customer_type": customer.customer_type.value,
        "account_number": customer.account_number,
        "signup_date": customer.signup_date.isoformat() if customer.signup_date else None,
        "activation_date": customer.activation_date.isoformat() if customer.activation_date else None,
        "cancellation_date": customer.cancellation_date.isoformat() if customer.cancellation_date else None,
        "tenure_days": customer.tenure_days,
        "pop": pop,
        "external_ids": {
            "splynx_id": customer.splynx_id,
            "erpnext_id": customer.erpnext_id,
            "chatwoot_contact_id": customer.chatwoot_contact_id,
        },
        "metrics": {
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "outstanding": outstanding,
            "open_tickets": open_tickets,
            "total_conversations": len(conversations),
        },
        "subscriptions": [
            {
                "id": s.id,
                "plan_name": s.plan_name,
                "price": float(s.price),
                "status": s.status.value,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "download_speed": s.download_speed,
                "upload_speed": s.upload_speed,
            }
            for s in subscriptions
        ],
        "recent_invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "total_amount": float(inv.total_amount),
                "amount_paid": float(inv.amount_paid or 0),
                "status": inv.status.value,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "days_overdue": inv.days_overdue,
            }
            for inv in invoices[:10]
        ],
        "recent_conversations": [
            {
                "id": c.id,
                "chatwoot_id": c.chatwoot_id,
                "status": c.status.value,
                "channel": c.channel,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "message_count": c.message_count,
            }
            for c in conversations[:10]
        ],
    }


@router.get("/churned", dependencies=[Depends(Require("explorer:read"))])
async def get_churned_customers(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    pop_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get list of churned customers with analysis."""
    query = db.query(Customer).filter(Customer.status == CustomerStatus.CANCELLED)

    if start_date:
        query = query.filter(Customer.cancellation_date >= datetime.fromisoformat(start_date))

    if end_date:
        query = query.filter(Customer.cancellation_date <= datetime.fromisoformat(end_date))

    if pop_id:
        query = query.filter(Customer.pop_id == pop_id)

    churned = query.order_by(Customer.cancellation_date.desc()).all()

    return {
        "total": len(churned),
        "data": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "pop_id": c.pop_id,
                "signup_date": c.signup_date.isoformat() if c.signup_date else None,
                "cancellation_date": c.cancellation_date.isoformat() if c.cancellation_date else None,
                "tenure_days": c.tenure_days,
            }
            for c in churned
        ],
    }
