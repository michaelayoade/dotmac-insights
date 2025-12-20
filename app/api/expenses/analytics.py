"""Corporate card analytics endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract

from app.database import get_db
from app.models.expense_management import (
    CorporateCard,
    CorporateCardTransaction,
    CorporateCardStatement,
    CorporateCardStatus,
    CardTransactionStatus,
    StatementStatus,
)
from app.auth import Require

router = APIRouter()


# =============================================================================
# OVERVIEW
# =============================================================================

@router.get("/analytics/overview", dependencies=[Depends(Require("expenses:read"))])
def get_card_analytics_overview(
    months: int = Query(default=6, le=24),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get overview metrics for corporate cards."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=months * 30)

    # Card counts
    total_cards = db.query(func.count(CorporateCard.id)).scalar() or 0
    active_cards = db.query(func.count(CorporateCard.id)).filter(
        CorporateCard.status == CorporateCardStatus.ACTIVE
    ).scalar() or 0
    suspended_cards = db.query(func.count(CorporateCard.id)).filter(
        CorporateCard.status == CorporateCardStatus.SUSPENDED
    ).scalar() or 0

    # Total credit limit
    total_limit = db.query(func.sum(CorporateCard.credit_limit)).filter(
        CorporateCard.status == CorporateCardStatus.ACTIVE
    ).scalar() or Decimal("0")

    # Transaction counts
    total_transactions = db.query(func.count(CorporateCardTransaction.id)).filter(
        CorporateCardTransaction.transaction_date >= start_dt
    ).scalar() or 0

    matched_transactions = db.query(func.count(CorporateCardTransaction.id)).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
        CorporateCardTransaction.status == CardTransactionStatus.MATCHED
    ).scalar() or 0

    unmatched_transactions = db.query(func.count(CorporateCardTransaction.id)).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
        CorporateCardTransaction.status.in_([
            CardTransactionStatus.IMPORTED,
            CardTransactionStatus.UNMATCHED
        ])
    ).scalar() or 0

    disputed_transactions = db.query(func.count(CorporateCardTransaction.id)).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
        CorporateCardTransaction.status == CardTransactionStatus.DISPUTED
    ).scalar() or 0

    personal_transactions = db.query(func.count(CorporateCardTransaction.id)).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
        CorporateCardTransaction.status == CardTransactionStatus.PERSONAL
    ).scalar() or 0

    # Total spend
    total_spend = db.query(func.sum(CorporateCardTransaction.amount)).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
        CorporateCardTransaction.status != CardTransactionStatus.EXCLUDED
    ).scalar() or Decimal("0")

    # Reconciliation rate
    reconciliation_rate = round(
        matched_transactions / total_transactions * 100, 1
    ) if total_transactions > 0 else 0

    return {
        "cards": {
            "total": total_cards,
            "active": active_cards,
            "suspended": suspended_cards,
            "total_credit_limit": float(total_limit),
        },
        "transactions": {
            "total": total_transactions,
            "matched": matched_transactions,
            "unmatched": unmatched_transactions,
            "disputed": disputed_transactions,
            "personal": personal_transactions,
            "reconciliation_rate": reconciliation_rate,
        },
        "spend": {
            "total": float(total_spend),
            "period_months": months,
        },
    }


# =============================================================================
# SPEND TREND
# =============================================================================

@router.get("/analytics/spend-trend", dependencies=[Depends(Require("expenses:read"))])
def get_spend_trend(
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get monthly spend trend."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=months * 30)

    spend = db.query(
        extract("year", CorporateCardTransaction.transaction_date).label("year"),
        extract("month", CorporateCardTransaction.transaction_date).label("month"),
        func.count(CorporateCardTransaction.id).label("transaction_count"),
        func.sum(CorporateCardTransaction.amount).label("total_spend"),
        func.sum(case(
            (CorporateCardTransaction.status == CardTransactionStatus.MATCHED, CorporateCardTransaction.amount),
            else_=Decimal("0")
        )).label("matched_spend"),
        func.sum(case(
            (CorporateCardTransaction.status == CardTransactionStatus.PERSONAL, CorporateCardTransaction.amount),
            else_=Decimal("0")
        )).label("personal_spend"),
    ).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
        CorporateCardTransaction.transaction_date <= end_dt,
        CorporateCardTransaction.status != CardTransactionStatus.EXCLUDED,
    ).group_by(
        extract("year", CorporateCardTransaction.transaction_date),
        extract("month", CorporateCardTransaction.transaction_date),
    ).order_by("year", "month").all()

    results: List[Dict[str, Any]] = []
    for row in spend:
        period = f"{int(row.year)}-{int(row.month):02d}"
        total = float(row.total_spend or 0)
        matched = float(row.matched_spend or 0)
        results.append({
            "period": period,
            "transaction_count": row.transaction_count,
            "total_spend": total,
            "matched_spend": matched,
            "personal_spend": float(row.personal_spend or 0),
            "reconciliation_rate": round(matched / total * 100, 1) if total > 0 else 0,
        })

    return results


# =============================================================================
# TOP MERCHANTS
# =============================================================================

@router.get("/analytics/top-merchants", dependencies=[Depends(Require("expenses:read"))])
def get_top_merchants(
    days: int = Query(default=90, le=365),
    limit: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get top merchants by spend."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days)

    merchants = db.query(
        CorporateCardTransaction.merchant_name,
        func.count(CorporateCardTransaction.id).label("transaction_count"),
        func.sum(CorporateCardTransaction.amount).label("total_spend"),
    ).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
        CorporateCardTransaction.merchant_name.isnot(None),
        CorporateCardTransaction.status != CardTransactionStatus.EXCLUDED,
    ).group_by(
        CorporateCardTransaction.merchant_name
    ).order_by(
        func.sum(CorporateCardTransaction.amount).desc()
    ).limit(limit).all()

    total_spend = db.query(func.sum(CorporateCardTransaction.amount)).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
        CorporateCardTransaction.status != CardTransactionStatus.EXCLUDED,
    ).scalar() or Decimal("0")

    return {
        "merchants": [
            {
                "merchant": row.merchant_name or "Unknown",
                "transaction_count": row.transaction_count,
                "total_spend": float(row.total_spend or 0),
                "percentage": round(float(row.total_spend or 0) / float(total_spend) * 100, 1) if total_spend > 0 else 0,
            }
            for row in merchants
        ],
        "total_spend": float(total_spend),
        "period_days": days,
    }


# =============================================================================
# BY CATEGORY (MCC CODE)
# =============================================================================

@router.get("/analytics/by-category", dependencies=[Depends(Require("expenses:read"))])
def get_by_category(
    days: int = Query(default=90, le=365),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get spend breakdown by merchant category code."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days)

    categories = db.query(
        CorporateCardTransaction.merchant_category_code,
        func.count(CorporateCardTransaction.id).label("transaction_count"),
        func.sum(CorporateCardTransaction.amount).label("total_spend"),
    ).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
        CorporateCardTransaction.status != CardTransactionStatus.EXCLUDED,
    ).group_by(
        CorporateCardTransaction.merchant_category_code
    ).order_by(
        func.sum(CorporateCardTransaction.amount).desc()
    ).limit(15).all()

    total_spend = db.query(func.sum(CorporateCardTransaction.amount)).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
        CorporateCardTransaction.status != CardTransactionStatus.EXCLUDED,
    ).scalar() or Decimal("0")

    # Map common MCC codes to readable names
    MCC_NAMES = {
        "5411": "Grocery Stores",
        "5812": "Restaurants",
        "5814": "Fast Food",
        "5541": "Gas Stations",
        "4121": "Taxi/Rideshare",
        "3000": "Airlines",
        "7011": "Hotels",
        "5311": "Department Stores",
        "5999": "Misc Retail",
        "7399": "Business Services",
        "5045": "Computers/Electronics",
        "5942": "Book Stores",
        "5912": "Drug Stores",
    }

    return {
        "categories": [
            {
                "mcc_code": row.merchant_category_code or "Unknown",
                "category_name": MCC_NAMES.get(row.merchant_category_code or "", row.merchant_category_code or "Other"),
                "transaction_count": row.transaction_count,
                "total_spend": float(row.total_spend or 0),
                "percentage": round(float(row.total_spend or 0) / float(total_spend) * 100, 1) if total_spend > 0 else 0,
            }
            for row in categories
        ],
        "total_spend": float(total_spend),
        "period_days": days,
    }


# =============================================================================
# CARD UTILIZATION
# =============================================================================

@router.get("/analytics/card-utilization", dependencies=[Depends(Require("expenses:read"))])
def get_card_utilization(
    days: int = Query(default=30, le=365),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get spend vs limit for each active card."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days)

    # Get active cards with their spend
    cards = db.query(CorporateCard).filter(
        CorporateCard.status == CorporateCardStatus.ACTIVE
    ).all()

    results = []
    for card in cards:
        spend = db.query(func.sum(CorporateCardTransaction.amount)).filter(
            CorporateCardTransaction.card_id == card.id,
            CorporateCardTransaction.transaction_date >= start_dt,
            CorporateCardTransaction.status != CardTransactionStatus.EXCLUDED,
        ).scalar() or Decimal("0")

        limit = float(card.credit_limit or 0)
        spend_float = float(spend)
        utilization = round(spend_float / limit * 100, 1) if limit > 0 else 0

        results.append({
            "card_id": card.id,
            "card_name": card.card_name,
            "card_last4": card.card_number_last4,
            "employee_id": card.employee_id,
            "credit_limit": limit,
            "spend": spend_float,
            "utilization_pct": utilization,
            "remaining": max(0, limit - spend_float),
        })

    # Sort by utilization descending
    results.sort(key=lambda x: x["utilization_pct"], reverse=True)
    return results


# =============================================================================
# TRANSACTION STATUS BREAKDOWN
# =============================================================================

@router.get("/analytics/status-breakdown", dependencies=[Depends(Require("expenses:read"))])
def get_status_breakdown(
    days: int = Query(default=30, le=365),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get transaction count and spend by status."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days)

    statuses = db.query(
        CorporateCardTransaction.status,
        func.count(CorporateCardTransaction.id).label("count"),
        func.sum(CorporateCardTransaction.amount).label("total"),
    ).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
    ).group_by(
        CorporateCardTransaction.status
    ).all()

    total_count = sum(int(row._mapping["count"]) for row in statuses)
    total_amount = sum(float(row._mapping["total"] or 0) for row in statuses)

    return {
        "by_status": [
            {
                "status": row._mapping["status"].value if row._mapping["status"] else "unknown",
                "count": int(row._mapping["count"]),
                "amount": float(row._mapping["total"] or 0),
                "count_pct": round(int(row._mapping["count"]) / total_count * 100, 1) if total_count > 0 else 0,
                "amount_pct": round(float(row._mapping["total"] or 0) / total_amount * 100, 1) if total_amount > 0 else 0,
            }
            for row in statuses
        ],
        "totals": {
            "count": total_count,
            "amount": total_amount,
        },
        "period_days": days,
    }


# =============================================================================
# TOP SPENDERS (BY EMPLOYEE/CARD)
# =============================================================================

@router.get("/analytics/top-spenders", dependencies=[Depends(Require("expenses:read"))])
def get_top_spenders(
    days: int = Query(default=30, le=365),
    limit: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get top spending cards/employees."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days)

    spenders = db.query(
        CorporateCard.id,
        CorporateCard.card_name,
        CorporateCard.card_number_last4,
        CorporateCard.employee_id,
        func.count(CorporateCardTransaction.id).label("transaction_count"),
        func.sum(CorporateCardTransaction.amount).label("total_spend"),
    ).join(
        CorporateCardTransaction, CorporateCardTransaction.card_id == CorporateCard.id
    ).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
        CorporateCardTransaction.status != CardTransactionStatus.EXCLUDED,
    ).group_by(
        CorporateCard.id,
        CorporateCard.card_name,
        CorporateCard.card_number_last4,
        CorporateCard.employee_id,
    ).order_by(
        func.sum(CorporateCardTransaction.amount).desc()
    ).limit(limit).all()

    return {
        "spenders": [
            {
                "card_id": row.id,
                "card_name": row.card_name,
                "card_last4": row.card_number_last4,
                "employee_id": row.employee_id,
                "transaction_count": row.transaction_count,
                "total_spend": float(row.total_spend or 0),
            }
            for row in spenders
        ],
        "period_days": days,
    }


# =============================================================================
# RECONCILIATION TREND
# =============================================================================

@router.get("/analytics/reconciliation-trend", dependencies=[Depends(Require("expenses:read"))])
def get_reconciliation_trend(
    months: int = Query(default=6, le=24),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get monthly reconciliation rate trend."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=months * 30)

    trend = db.query(
        extract("year", CorporateCardTransaction.transaction_date).label("year"),
        extract("month", CorporateCardTransaction.transaction_date).label("month"),
        func.count(CorporateCardTransaction.id).label("total"),
        func.sum(case(
            (CorporateCardTransaction.status == CardTransactionStatus.MATCHED, 1),
            else_=0
        )).label("matched"),
        func.sum(case(
            (CorporateCardTransaction.status.in_([
                CardTransactionStatus.IMPORTED,
                CardTransactionStatus.UNMATCHED
            ]), 1),
            else_=0
        )).label("unmatched"),
    ).filter(
        CorporateCardTransaction.transaction_date >= start_dt,
        CorporateCardTransaction.transaction_date <= end_dt,
    ).group_by(
        extract("year", CorporateCardTransaction.transaction_date),
        extract("month", CorporateCardTransaction.transaction_date),
    ).order_by("year", "month").all()

    results = []
    for row in trend:
        period = f"{int(row.year)}-{int(row.month):02d}"
        total = row.total or 0
        matched = row.matched or 0
        results.append({
            "period": period,
            "total": total,
            "matched": matched,
            "unmatched": row.unmatched or 0,
            "reconciliation_rate": round(matched / total * 100, 1) if total > 0 else 0,
        })

    return results


# =============================================================================
# STATEMENT SUMMARY
# =============================================================================

@router.get("/analytics/statement-summary", dependencies=[Depends(Require("expenses:read"))])
def get_statement_summary(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get summary of statement reconciliation status."""
    total = db.query(func.count(CorporateCardStatement.id)).scalar() or 0
    open_count = db.query(func.count(CorporateCardStatement.id)).filter(
        CorporateCardStatement.status == StatementStatus.OPEN
    ).scalar() or 0
    reconciled = db.query(func.count(CorporateCardStatement.id)).filter(
        CorporateCardStatement.status == StatementStatus.RECONCILED
    ).scalar() or 0
    closed = db.query(func.count(CorporateCardStatement.id)).filter(
        CorporateCardStatement.status == StatementStatus.CLOSED
    ).scalar() or 0

    # Aggregates
    totals = db.query(
        func.sum(CorporateCardStatement.total_amount).label("total_amount"),
        func.sum(CorporateCardStatement.transaction_count).label("total_transactions"),
        func.sum(CorporateCardStatement.matched_count).label("total_matched"),
        func.sum(CorporateCardStatement.unmatched_count).label("total_unmatched"),
    ).first()

    return {
        "statements": {
            "total": total,
            "open": open_count,
            "reconciled": reconciled,
            "closed": closed,
        },
        "aggregates": {
            "total_amount": float(totals.total_amount or 0) if totals else 0,
            "total_transactions": int(totals.total_transactions or 0) if totals else 0,
            "total_matched": int(totals.total_matched or 0) if totals else 0,
            "total_unmatched": int(totals.total_unmatched or 0) if totals else 0,
        },
    }
