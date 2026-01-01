"""
Shared dependencies for accounting routes.

This module contains common imports, helpers, and permission dependencies
used across all accounting route modules.
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import selectinload

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request, htmx_toast, set_flash, validate_csrf

# Models - Core
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.models.contact import Contact

# Models - Accounting
from app.models.accounting import (
    Account, AccountType, GLEntry, JournalEntry, JournalEntryItem, JournalEntryType,
    BankAccount, BankTransaction, BankTransactionStatus, BankReconciliation, BankReconciliationStatus,
    FiscalYear, Supplier, PurchaseInvoice, PurchaseInvoiceStatus, CostCenter,
)

# Models - Accounting Extended
from app.models.accounting_ext import (
    FiscalPeriod, FiscalPeriodStatus, FiscalPeriodType, AuditLog, AuditAction,
    ApprovalWorkflow, ApprovalStep, DocumentApproval, ApprovalHistory, ApprovalStatus, ApprovalMode,
    AccountingControl,
)

# Models - Auth and Payments
from app.models.auth import User
from app.models.supplier_payment import SupplierPayment, SupplierPaymentStatus

# Permission dependencies
RequireAccountingRead = Depends(require_scope("accounting:read"))
RequireAccountingWrite = Depends(require_scope("accounting:write"))

# Template environment
templates = get_template_env()


# Common helper functions
def get_currency_options() -> list:
    """Get list of currency options."""
    return [
        {"value": "NGN", "label": "NGN - Nigerian Naira"},
        {"value": "USD", "label": "USD - US Dollar"},
        {"value": "GBP", "label": "GBP - British Pound"},
        {"value": "EUR", "label": "EUR - Euro"},
    ]


def form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile) or value is None:
        return default
    return str(value).strip()


def form_int(form: Any, key: str, default: Optional[int] = None) -> Optional[int]:
    value = form.get(key, default)
    if isinstance(value, UploadFile) or value in ("", None):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def form_decimal(form: Any, key: str, default: Optional[Decimal] = None) -> Optional[Decimal]:
    value = form.get(key, default)
    if isinstance(value, UploadFile) or value in ("", None):
        return default
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return default
