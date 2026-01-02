"""Ledger endpoints: Chart of Accounts, Account Details, GL Entries.

This module provides the REST API for ledger management.
Business logic is delegated to LedgerService.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth import Require, get_current_principal, Principal
from app.database import get_db
from app.models.accounting import AccountType
from app.services.accounting.ledger import LedgerService
from app.services.accounting.ledger_types import (
    AccountCreateData,
    AccountFilters,
    AccountLedgerFilters,
    AccountUpdateData,
    GLEntryCreateData,
    GLEntryFilters,
    GLEntryUpdateData,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

from .helpers import parse_date, serialize_account

router = APIRouter()


# ============= SERVICE DEPENDENCY =============

def get_ledger_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> LedgerService:
    """Create a LedgerService instance for dependency injection."""
    return LedgerService(db, principal)


# ============= PYDANTIC SCHEMAS =============

class AccountCreateRequest(BaseModel):
    account_name: str
    account_number: Optional[str] = None
    parent_account: Optional[str] = None
    root_type: Optional[str] = None
    account_type: Optional[str] = None
    company: Optional[str] = None
    is_group: bool = False
    disabled: bool = False
    balance_must_be: Optional[str] = None


class AccountUpdateRequest(BaseModel):
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    parent_account: Optional[str] = None
    root_type: Optional[str] = None
    account_type: Optional[str] = None
    company: Optional[str] = None
    is_group: Optional[bool] = None
    disabled: Optional[bool] = None
    balance_must_be: Optional[str] = None


class GLEntryCreateRequest(BaseModel):
    posting_date: Optional[date] = None
    account: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None
    debit: Optional[Decimal] = Decimal("0")
    credit: Optional[Decimal] = Decimal("0")
    debit_in_account_currency: Optional[Decimal] = None
    credit_in_account_currency: Optional[Decimal] = None
    voucher_type: Optional[str] = None
    voucher_no: Optional[str] = None
    cost_center: Optional[str] = None
    company: Optional[str] = None
    fiscal_year: Optional[str] = None
    is_cancelled: bool = False

    @field_validator(
        "debit",
        "credit",
        "debit_in_account_currency",
        "credit_in_account_currency",
        mode="before",
    )
    def _to_decimal(cls, value):
        if value is None:
            return None
        return Decimal(str(value))


class GLEntryUpdateRequest(BaseModel):
    posting_date: Optional[date] = None
    account: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None
    debit: Optional[Decimal] = None
    credit: Optional[Decimal] = None
    debit_in_account_currency: Optional[Decimal] = None
    credit_in_account_currency: Optional[Decimal] = None
    voucher_type: Optional[str] = None
    voucher_no: Optional[str] = None
    cost_center: Optional[str] = None
    company: Optional[str] = None
    fiscal_year: Optional[str] = None
    is_cancelled: Optional[bool] = None

    @field_validator(
        "debit",
        "credit",
        "debit_in_account_currency",
        "credit_in_account_currency",
        mode="before",
    )
    def _to_decimal(cls, value):
        if value is None:
            return None
        return Decimal(str(value))


# ============= HELPER FUNCTIONS =============

def _parse_root_type(root_type: Optional[str]) -> Optional[AccountType]:
    """Parse root type string to enum."""
    if not root_type:
        return None
    try:
        return AccountType(root_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid root_type: {root_type}"
        )


# ============= ACCOUNTS LIST =============

@router.get("/accounts", dependencies=[Depends(Require("accounting:read"))])
def list_accounts(
    root_type: Optional[str] = None,
    account_type: Optional[str] = None,
    is_group: Optional[bool] = None,
    include_disabled: bool = False,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: LedgerService = Depends(get_ledger_service),
) -> Dict[str, Any]:
    """List all accounts with filtering and pagination."""
    try:
        filters = AccountFilters(
            root_type=_parse_root_type(root_type),
            account_type=account_type,
            is_group=is_group,
            include_disabled=include_disabled,
            search=search,
        )
        pagination = PaginationParams(offset=offset, limit=limit)

        result = service.list_accounts(filters, pagination)

        return {
            "total": result.total,
            "limit": limit,
            "offset": offset,
            "accounts": [serialize_account(acc) for acc in result.items],
        }
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= ACCOUNT DETAIL =============

@router.get(
    "/accounts/{account_id}", dependencies=[Depends(Require("accounting:read"))]
)
def get_account_detail(
    account_id: int,
    include_ledger: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    service: LedgerService = Depends(get_ledger_service),
) -> Dict[str, Any]:
    """Get detailed account information with optional transaction ledger."""
    try:
        account = service.get_account(account_id)
        balance_info = service.get_account_balance(account)

        result: Dict[str, Any] = {
            "id": account.id,
            "erpnext_id": account.erpnext_id,
            "name": account.account_name,
            "account_number": account.account_number,
            "parent_account": account.parent_account,
            "root_type": account.root_type.value if account.root_type else None,
            "account_type": account.account_type,
            "is_group": account.is_group,
            "disabled": account.disabled,
            "normal_balance": balance_info.normal_balance,
            "total_debit": float(balance_info.total_debit),
            "total_credit": float(balance_info.total_credit),
            "balance": float(balance_info.balance),
            "balance_type": balance_info.balance_type,
        }

        if include_ledger:
            ledger_filters = AccountLedgerFilters(
                start_date=parse_date(start_date, "start_date") if start_date else None,
                end_date=parse_date(end_date, "end_date") if end_date else None,
            )
            ledger_pagination = PaginationParams(offset=0, limit=limit)
            ledger_result = service.get_account_ledger(
                account_id, ledger_filters, ledger_pagination
            )

            result["ledger"] = [
                {
                    "id": e.id,
                    "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                    "party_type": e.party_type,
                    "party": e.party,
                    "debit": float(e.debit),
                    "credit": float(e.credit),
                    "voucher_type": e.voucher_type,
                    "voucher_no": e.voucher_no,
                    "cost_center": e.cost_center,
                }
                for e in ledger_result.entries
            ]
            result["ledger_count"] = len(ledger_result.entries)

        return result
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= ACCOUNT CRUD =============

@router.post("/accounts", dependencies=[Depends(Require("accounting:write"))])
def create_account(
    payload: AccountCreateRequest,
    db: Session = Depends(get_db),
    service: LedgerService = Depends(get_ledger_service),
) -> Dict[str, Any]:
    """Create a chart of accounts entry locally."""
    try:
        data = AccountCreateData(
            account_name=payload.account_name,
            account_number=payload.account_number,
            parent_account=payload.parent_account,
            root_type=_parse_root_type(payload.root_type),
            account_type=payload.account_type,
            company=payload.company,
            is_group=payload.is_group,
            disabled=payload.disabled,
            balance_must_be=payload.balance_must_be,
        )
        account = service.create_account(data)
        db.commit()
        db.refresh(account)
        return {"id": account.id}
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch(
    "/accounts/{account_id}", dependencies=[Depends(Require("accounting:write"))]
)
def update_account(
    account_id: int,
    payload: AccountUpdateRequest,
    db: Session = Depends(get_db),
    service: LedgerService = Depends(get_ledger_service),
) -> Dict[str, Any]:
    """Update a chart of accounts entry locally."""
    try:
        data = AccountUpdateData(
            account_name=payload.account_name,
            account_number=payload.account_number,
            parent_account=payload.parent_account,
            root_type=_parse_root_type(payload.root_type) if payload.root_type else None,
            account_type=payload.account_type,
            company=payload.company,
            is_group=payload.is_group,
            disabled=payload.disabled,
            balance_must_be=payload.balance_must_be,
        )
        account = service.update_account(account_id, data)
        db.commit()
        db.refresh(account)
        return {"id": account.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete(
    "/accounts/{account_id}", dependencies=[Depends(Require("accounting:write"))]
)
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    service: LedgerService = Depends(get_ledger_service),
) -> Dict[str, Any]:
    """Disable a chart of accounts entry."""
    try:
        service.disable_account(account_id)
        db.commit()
        return {"status": "disabled", "account_id": account_id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= ACCOUNT LEDGER =============

@router.get(
    "/accounts/{account_id}/ledger",
    dependencies=[Depends(Require("accounting:read"))],
)
def get_account_ledger(
    account_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    party_type: Optional[str] = None,
    party: Optional[str] = None,
    voucher_type: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    service: LedgerService = Depends(get_ledger_service),
) -> Dict[str, Any]:
    """Get ledger (GL entries) for a specific account with running balance."""
    try:
        filters = AccountLedgerFilters(
            start_date=parse_date(start_date, "start_date") if start_date else None,
            end_date=parse_date(end_date, "end_date") if end_date else None,
            party_type=party_type,
            party=party,
            voucher_type=voucher_type,
        )
        pagination = PaginationParams(offset=offset, limit=limit)

        result = service.get_account_ledger(account_id, filters, pagination)

        return {
            "account": {
                "id": result.account_id,
                "name": result.account_name,
                "root_type": result.root_type,
            },
            "period": {
                "start_date": result.start_date.isoformat() if result.start_date else None,
                "end_date": result.end_date.isoformat() if result.end_date else None,
            },
            "opening_balance": float(result.opening_balance),
            "closing_balance": float(result.closing_balance),
            "total": result.total,
            "limit": limit,
            "offset": offset,
            "entries": [
                {
                    "id": e.id,
                    "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                    "party_type": e.party_type,
                    "party": e.party,
                    "debit": float(e.debit),
                    "credit": float(e.credit),
                    "balance": float(e.balance),
                    "voucher_type": e.voucher_type,
                    "voucher_no": e.voucher_no,
                    "cost_center": e.cost_center,
                }
                for e in result.entries
            ],
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= CHART OF ACCOUNTS =============

@router.get("/chart-of-accounts", dependencies=[Depends(Require("accounting:read"))])
def get_chart_of_accounts(
    root_type: Optional[str] = None,
    include_disabled: bool = False,
    include_balances: bool = True,
    as_of_date: Optional[str] = None,
    service: LedgerService = Depends(get_ledger_service),
) -> Dict[str, Any]:
    """Get chart of accounts as hierarchical tree with balances."""
    root_type_enum = _parse_root_type(root_type) if root_type else None
    cutoff = parse_date(as_of_date, "as_of_date") if as_of_date else None

    result = service.get_chart_of_accounts(
        root_type=root_type_enum,
        include_disabled=include_disabled,
        include_balances=include_balances,
        as_of_date=cutoff,
    )

    # Convert tree nodes to dicts
    def tree_to_dict(nodes):
        return [
            {
                "id": n.id,
                "name": n.name,
                "account_number": n.account_number,
                "root_type": n.root_type,
                "account_type": n.account_type,
                "is_group": n.is_group,
                "disabled": n.disabled,
                "balance": n.balance,
                "children": tree_to_dict(n.children) if n.children else [],
            }
            for n in nodes
        ]

    return {
        "total": result["total"],
        "by_root_type": result["by_root_type"],
        "accounts": result["accounts"],
        "tree": tree_to_dict(result["tree"]),
    }


# ============= GL ENTRIES LIST =============

@router.get("/gl-entries", dependencies=[Depends(Require("accounting:read"))])
def list_gl_entries(
    account: Optional[str] = None,
    voucher_type: Optional[str] = None,
    voucher_no: Optional[str] = None,
    party_type: Optional[str] = None,
    party: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    is_cancelled: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(
        default="posting_date",
        description="posting_date,account,debit,credit",
    ),
    sort_dir: Optional[str] = Query(default="desc"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: LedgerService = Depends(get_ledger_service),
) -> Dict[str, Any]:
    """List GL entries with filtering and sorting."""
    try:
        filters = GLEntryFilters(
            account=account,
            voucher_type=voucher_type,
            voucher_no=voucher_no,
            party_type=party_type,
            party=party,
            start_date=parse_date(start_date, "start_date") if start_date else None,
            end_date=parse_date(end_date, "end_date") if end_date else None,
            is_cancelled=is_cancelled,
            search=search,
            sort_by=sort_by or "posting_date",
            sort_dir=sort_dir or "desc",
        )
        pagination = PaginationParams(offset=offset, limit=limit)

        result = service.list_gl_entries(filters, pagination)

        return {
            "total": result.total,
            "limit": limit,
            "offset": offset,
            "data": [
                {
                    "id": e.id,
                    "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                    "account": e.account,
                    "party_type": e.party_type,
                    "party": e.party,
                    "debit": float(e.debit),
                    "credit": float(e.credit),
                    "voucher_type": e.voucher_type,
                    "voucher_no": e.voucher_no,
                    "cost_center": e.cost_center,
                    "is_cancelled": e.is_cancelled,
                }
                for e in result.items
            ],
        }
    except ValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= GL ENTRY DETAIL =============

@router.get(
    "/gl-entries/{entry_id}", dependencies=[Depends(Require("accounting:read"))]
)
def get_gl_entry_detail(
    entry_id: int,
    service: LedgerService = Depends(get_ledger_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get single GL entry detail."""
    from app.models.accounting import Account

    try:
        entry = service.get_gl_entry(entry_id)

        # Get account details
        account = db.query(Account).filter(Account.erpnext_id == entry.account).first()

        return {
            "id": entry.id,
            "erpnext_id": entry.erpnext_id,
            "posting_date": entry.posting_date.isoformat() if entry.posting_date else None,
            "account": entry.account,
            "account_name": account.account_name if account else None,
            "root_type": account.root_type.value if account and account.root_type else None,
            "party_type": entry.party_type,
            "party": entry.party,
            "debit": float(entry.debit),
            "credit": float(entry.credit),
            "voucher_type": entry.voucher_type,
            "voucher_no": entry.voucher_no,
            "cost_center": entry.cost_center,
            "fiscal_year": entry.fiscal_year,
            "is_cancelled": entry.is_cancelled,
            "company": entry.company,
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= GL ENTRY CRUD =============

@router.post("/gl-entries", dependencies=[Depends(Require("accounting:write"))])
def create_gl_entry(
    payload: GLEntryCreateRequest,
    db: Session = Depends(get_db),
    service: LedgerService = Depends(get_ledger_service),
) -> Dict[str, Any]:
    """Create a GL entry locally."""
    data = GLEntryCreateData(
        posting_date=payload.posting_date,
        account=payload.account,
        party_type=payload.party_type,
        party=payload.party,
        debit=payload.debit or Decimal("0"),
        credit=payload.credit or Decimal("0"),
        debit_in_account_currency=payload.debit_in_account_currency,
        credit_in_account_currency=payload.credit_in_account_currency,
        voucher_type=payload.voucher_type,
        voucher_no=payload.voucher_no,
        cost_center=payload.cost_center,
        company=payload.company,
        fiscal_year=payload.fiscal_year,
        is_cancelled=payload.is_cancelled,
    )
    entry = service.create_gl_entry(data)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id}


@router.patch(
    "/gl-entries/{entry_id}", dependencies=[Depends(Require("accounting:write"))]
)
def update_gl_entry(
    entry_id: int,
    payload: GLEntryUpdateRequest,
    db: Session = Depends(get_db),
    service: LedgerService = Depends(get_ledger_service),
) -> Dict[str, Any]:
    """Update a GL entry locally."""
    try:
        data = GLEntryUpdateData(
            posting_date=payload.posting_date,
            account=payload.account,
            party_type=payload.party_type,
            party=payload.party,
            debit=payload.debit,
            credit=payload.credit,
            debit_in_account_currency=payload.debit_in_account_currency,
            credit_in_account_currency=payload.credit_in_account_currency,
            voucher_type=payload.voucher_type,
            voucher_no=payload.voucher_no,
            cost_center=payload.cost_center,
            company=payload.company,
            fiscal_year=payload.fiscal_year,
            is_cancelled=payload.is_cancelled,
        )
        entry = service.update_gl_entry(entry_id, data)
        db.commit()
        db.refresh(entry)
        return {"id": entry.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete(
    "/gl-entries/{entry_id}", dependencies=[Depends(Require("accounting:write"))]
)
def delete_gl_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    service: LedgerService = Depends(get_ledger_service),
) -> Dict[str, Any]:
    """Delete a GL entry."""
    try:
        service.delete_gl_entry(entry_id)
        db.commit()
        return {"status": "deleted", "gl_entry_id": entry_id}
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


# ============= ACCOUNT TYPES =============

@router.get("/account-types", dependencies=[Depends(Require("accounting:read"))])
def get_account_types(
    service: LedgerService = Depends(get_ledger_service),
) -> Dict[str, Any]:
    """Get summary of accounts grouped by account type."""
    return service.get_account_types_summary()
