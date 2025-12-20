"""Accounting sync functions for ERPNext.

This module handles syncing of accounting-related entities:
- Bank Accounts, Bank Transactions
- Chart of Accounts (Account)
- Journal Entries, GL Entries
- Purchase Invoices, Sales Invoices
- Payments, Expenses
- Suppliers, Cost Centers, Fiscal Years
- Modes of Payment
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx
import structlog

from sqlalchemy import func

from app.models.accounting import (
    Account,
    AccountType,
    BankAccount,
    BankTransaction,
    BankTransactionStatus,
    CostCenter,
    FiscalYear,
    GLEntry,
    JournalEntry,
    JournalEntryType,
    ModeOfPayment,
    PaymentModeType,
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    Supplier,
)
from app.models.customer import Customer
from app.models.employee import Employee
from app.models.expense import Expense, ExpenseStatus
from app.models.invoice import Invoice, InvoiceSource, InvoiceStatus
from app.models.payment import Payment, PaymentMethod, PaymentSource, PaymentStatus
from app.models.project import Project

if TYPE_CHECKING:
    from app.sync.erpnext import ERPNextSync

logger = structlog.get_logger()


async def sync_bank_accounts(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync bank accounts from ERPNext."""
    sync_client.start_sync("bank_accounts", "full" if full_sync else "incremental")

    try:
        bank_accounts = await sync_client._fetch_all_doctype(
            client,
            "Bank Account",
            fields=["*"],
        )

        for ba_data in bank_accounts:
            erpnext_id = ba_data.get("name")
            existing = sync_client.db.query(BankAccount).filter(
                BankAccount.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.account_name = ba_data.get("account_name", "")
                existing.bank = ba_data.get("bank")
                existing.bank_account_no = ba_data.get("bank_account_no")
                existing.account = ba_data.get("account")
                existing.company = ba_data.get("company")
                existing.currency = ba_data.get("currency", "NGN")
                existing.is_company_account = ba_data.get("is_company_account", 1) == 1
                existing.is_default = ba_data.get("is_default", 0) == 1
                existing.disabled = ba_data.get("disabled", 0) == 1
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                bank_account = BankAccount(
                    erpnext_id=erpnext_id,
                    account_name=ba_data.get("account_name", ""),
                    bank=ba_data.get("bank"),
                    bank_account_no=ba_data.get("bank_account_no"),
                    account=ba_data.get("account"),
                    company=ba_data.get("company"),
                    currency=ba_data.get("currency", "NGN"),
                    is_company_account=ba_data.get("is_company_account", 1) == 1,
                    is_default=ba_data.get("is_default", 0) == 1,
                    disabled=ba_data.get("disabled", 0) == 1,
                )
                sync_client.db.add(bank_account)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_accounts(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync chart of accounts from ERPNext."""
    sync_client.start_sync("accounts", "full" if full_sync else "incremental")

    try:
        accounts = await sync_client._fetch_all_doctype(
            client,
            "Account",
            fields=["*"],
        )

        for acc_data in accounts:
            erpnext_id = acc_data.get("name")
            existing = sync_client.db.query(Account).filter(
                Account.erpnext_id == erpnext_id
            ).first()

            # Map root type
            root_type_str = (acc_data.get("root_type", "") or "").lower()
            root_type_map = {
                "asset": AccountType.ASSET,
                "liability": AccountType.LIABILITY,
                "equity": AccountType.EQUITY,
                "income": AccountType.INCOME,
                "expense": AccountType.EXPENSE,
            }
            root_type = root_type_map.get(root_type_str)

            if existing:
                existing.account_name = acc_data.get("account_name", "")
                existing.account_number = acc_data.get("account_number")
                existing.parent_account = acc_data.get("parent_account")
                existing.root_type = root_type
                existing.account_type = acc_data.get("account_type")
                existing.company = acc_data.get("company")
                existing.is_group = acc_data.get("is_group", 0) == 1
                existing.disabled = acc_data.get("disabled", 0) == 1
                existing.balance_must_be = acc_data.get("balance_must_be")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                account = Account(
                    erpnext_id=erpnext_id,
                    account_name=acc_data.get("account_name", ""),
                    account_number=acc_data.get("account_number"),
                    parent_account=acc_data.get("parent_account"),
                    root_type=root_type,
                    account_type=acc_data.get("account_type"),
                    company=acc_data.get("company"),
                    is_group=acc_data.get("is_group", 0) == 1,
                    disabled=acc_data.get("disabled", 0) == 1,
                    balance_must_be=acc_data.get("balance_must_be"),
                )
                sync_client.db.add(account)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_journal_entries(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync journal entries from ERPNext."""
    sync_client.start_sync("journal_entries", "full" if full_sync else "incremental")

    try:
        entries = await sync_client._fetch_all_doctype(
            client,
            "Journal Entry",
            fields=["*"],
        )

        batch_size = 500
        for i, entry_data in enumerate(entries, 1):
            erpnext_id = entry_data.get("name")
            existing = sync_client.db.query(JournalEntry).filter(
                JournalEntry.erpnext_id == erpnext_id
            ).first()

            # Map voucher type
            vtype_str = (entry_data.get("voucher_type", "") or "").lower().replace(" ", "_")
            vtype_map = {
                "journal_entry": JournalEntryType.JOURNAL_ENTRY,
                "bank_entry": JournalEntryType.BANK_ENTRY,
                "cash_entry": JournalEntryType.CASH_ENTRY,
                "credit_card_entry": JournalEntryType.CREDIT_CARD_ENTRY,
                "debit_note": JournalEntryType.DEBIT_NOTE,
                "credit_note": JournalEntryType.CREDIT_NOTE,
                "contra_entry": JournalEntryType.CONTRA_ENTRY,
                "excise_entry": JournalEntryType.EXCISE_ENTRY,
                "write_off_entry": JournalEntryType.WRITE_OFF_ENTRY,
                "opening_entry": JournalEntryType.OPENING_ENTRY,
                "depreciation_entry": JournalEntryType.DEPRECIATION_ENTRY,
                "exchange_rate_revaluation": JournalEntryType.EXCHANGE_RATE_REVALUATION,
            }
            voucher_type = vtype_map.get(vtype_str, JournalEntryType.JOURNAL_ENTRY)

            if existing:
                existing.voucher_type = voucher_type
                existing.company = entry_data.get("company")
                existing.total_debit = Decimal(str(entry_data.get("total_debit", 0) or 0))
                existing.total_credit = Decimal(str(entry_data.get("total_credit", 0) or 0))
                existing.cheque_no = entry_data.get("cheque_no")
                existing.user_remark = entry_data.get("user_remark")
                existing.is_opening = entry_data.get("is_opening") == "Yes"
                existing.docstatus = entry_data.get("docstatus", 0)
                existing.last_synced_at = datetime.utcnow()

                if entry_data.get("posting_date"):
                    try:
                        existing.posting_date = datetime.fromisoformat(entry_data["posting_date"])
                    except (ValueError, TypeError):
                        pass

                if entry_data.get("cheque_date"):
                    try:
                        existing.cheque_date = datetime.fromisoformat(entry_data["cheque_date"])
                    except (ValueError, TypeError):
                        pass

                sync_client.increment_updated()
            else:
                journal_entry = JournalEntry(
                    erpnext_id=erpnext_id,
                    voucher_type=voucher_type,
                    company=entry_data.get("company"),
                    total_debit=float(entry_data.get("total_debit", 0) or 0),
                    total_credit=float(entry_data.get("total_credit", 0) or 0),
                    cheque_no=entry_data.get("cheque_no"),
                    user_remark=entry_data.get("user_remark"),
                    is_opening=entry_data.get("is_opening") == "Yes",
                    docstatus=entry_data.get("docstatus", 0),
                )

                if entry_data.get("posting_date"):
                    try:
                        journal_entry.posting_date = datetime.fromisoformat(entry_data["posting_date"])
                    except (ValueError, TypeError):
                        pass

                if entry_data.get("cheque_date"):
                    try:
                        journal_entry.cheque_date = datetime.fromisoformat(entry_data["cheque_date"])
                    except (ValueError, TypeError):
                        pass

                sync_client.db.add(journal_entry)
                sync_client.increment_created()

            # Batch commit
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("journal_entries_batch_committed", processed=i, total=len(entries))

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_purchase_invoices(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync purchase invoices from ERPNext."""
    sync_client.start_sync("purchase_invoices", "full" if full_sync else "incremental")

    try:
        invoices = await sync_client._fetch_all_doctype(
            client,
            "Purchase Invoice",
            fields=["*"],
        )

        for inv_data in invoices:
            erpnext_id = inv_data.get("name")
            existing = sync_client.db.query(PurchaseInvoice).filter(
                PurchaseInvoice.erpnext_id == erpnext_id
            ).first()

            # Map status
            status_str = (inv_data.get("status", "") or "").lower()
            status_map = {
                "draft": PurchaseInvoiceStatus.DRAFT,
                "submitted": PurchaseInvoiceStatus.SUBMITTED,
                "paid": PurchaseInvoiceStatus.PAID,
                "unpaid": PurchaseInvoiceStatus.UNPAID,
                "overdue": PurchaseInvoiceStatus.OVERDUE,
                "cancelled": PurchaseInvoiceStatus.CANCELLED,
                "return": PurchaseInvoiceStatus.RETURN,
            }
            status = status_map.get(status_str, PurchaseInvoiceStatus.DRAFT)

            if existing:
                existing.supplier = inv_data.get("supplier")
                existing.supplier_name = inv_data.get("supplier_name")
                existing.company = inv_data.get("company")
                existing.grand_total = Decimal(str(inv_data.get("grand_total", 0) or 0))
                existing.outstanding_amount = Decimal(str(inv_data.get("outstanding_amount", 0) or 0))
                existing.paid_amount = Decimal(str(inv_data.get("paid_amount", 0) or 0))
                existing.currency = inv_data.get("currency", "NGN")
                existing.status = status
                existing.docstatus = inv_data.get("docstatus", 0)
                existing.last_synced_at = datetime.utcnow()

                if inv_data.get("posting_date"):
                    try:
                        existing.posting_date = datetime.fromisoformat(inv_data["posting_date"])
                    except (ValueError, TypeError):
                        pass

                if inv_data.get("due_date"):
                    try:
                        existing.due_date = datetime.fromisoformat(inv_data["due_date"])
                    except (ValueError, TypeError):
                        pass

                sync_client.increment_updated()
            else:
                purchase_invoice = PurchaseInvoice(
                    erpnext_id=erpnext_id,
                    supplier=inv_data.get("supplier"),
                    supplier_name=inv_data.get("supplier_name"),
                    company=inv_data.get("company"),
                    grand_total=float(inv_data.get("grand_total", 0) or 0),
                    outstanding_amount=float(inv_data.get("outstanding_amount", 0) or 0),
                    paid_amount=float(inv_data.get("paid_amount", 0) or 0),
                    currency=inv_data.get("currency", "NGN"),
                    status=status,
                    docstatus=inv_data.get("docstatus", 0),
                )

                if inv_data.get("posting_date"):
                    try:
                        purchase_invoice.posting_date = datetime.fromisoformat(inv_data["posting_date"])
                    except (ValueError, TypeError):
                        pass

                if inv_data.get("due_date"):
                    try:
                        purchase_invoice.due_date = datetime.fromisoformat(inv_data["due_date"])
                    except (ValueError, TypeError):
                        pass

                sync_client.db.add(purchase_invoice)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_gl_entries(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync general ledger entries from ERPNext."""
    sync_client.start_sync("gl_entries", "full" if full_sync else "incremental")

    try:
        gl_entries = await sync_client._fetch_all_doctype(
            client,
            "GL Entry",
            fields=["*"],
        )

        batch_size = 500
        for i, gl_data in enumerate(gl_entries, 1):
            erpnext_id = gl_data.get("name")
            existing = sync_client.db.query(GLEntry).filter(
                GLEntry.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.account = gl_data.get("account")
                existing.party_type = gl_data.get("party_type")
                existing.party = gl_data.get("party")
                existing.debit = Decimal(str(gl_data.get("debit", 0) or 0))
                existing.credit = Decimal(str(gl_data.get("credit", 0) or 0))
                existing.debit_in_account_currency = Decimal(str(gl_data.get("debit_in_account_currency", 0) or 0))
                existing.credit_in_account_currency = Decimal(str(gl_data.get("credit_in_account_currency", 0) or 0))
                existing.voucher_type = gl_data.get("voucher_type")
                existing.voucher_no = gl_data.get("voucher_no")
                existing.cost_center = gl_data.get("cost_center")
                existing.company = gl_data.get("company")
                existing.fiscal_year = gl_data.get("fiscal_year")
                existing.is_cancelled = gl_data.get("is_cancelled", 0) == 1
                existing.last_synced_at = datetime.utcnow()

                if gl_data.get("posting_date"):
                    try:
                        existing.posting_date = datetime.fromisoformat(gl_data["posting_date"])
                    except (ValueError, TypeError):
                        pass

                sync_client.increment_updated()
            else:
                gl_entry = GLEntry(
                    erpnext_id=erpnext_id,
                    account=gl_data.get("account"),
                    party_type=gl_data.get("party_type"),
                    party=gl_data.get("party"),
                    debit=float(gl_data.get("debit", 0) or 0),
                    credit=float(gl_data.get("credit", 0) or 0),
                    debit_in_account_currency=float(gl_data.get("debit_in_account_currency", 0) or 0),
                    credit_in_account_currency=float(gl_data.get("credit_in_account_currency", 0) or 0),
                    voucher_type=gl_data.get("voucher_type"),
                    voucher_no=gl_data.get("voucher_no"),
                    cost_center=gl_data.get("cost_center"),
                    company=gl_data.get("company"),
                    fiscal_year=gl_data.get("fiscal_year"),
                    is_cancelled=gl_data.get("is_cancelled", 0) == 1,
                )

                if gl_data.get("posting_date"):
                    try:
                        gl_entry.posting_date = datetime.fromisoformat(gl_data["posting_date"])
                    except (ValueError, TypeError):
                        pass

                sync_client.db.add(gl_entry)
                sync_client.increment_created()

            # Batch commit for large datasets
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("gl_entries_batch_committed", processed=i, total=len(gl_entries))

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_bank_transactions(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync bank transactions from ERPNext - imported bank statement lines."""
    sync_client.start_sync("bank_transactions", "full" if full_sync else "incremental")

    try:
        transactions = await sync_client._fetch_all_doctype(
            client,
            "Bank Transaction",
            fields=["*"],
        )

        # Pre-fetch bank accounts for FK linking
        bank_accounts_by_erpnext_id = {
            ba.erpnext_id: ba.id
            for ba in sync_client.db.query(BankAccount).filter(
                BankAccount.erpnext_id.isnot(None)
            ).all()
        }

        batch_size = 500
        for i, txn_data in enumerate(transactions, 1):
            erpnext_id = txn_data.get("name")
            existing = sync_client.db.query(BankTransaction).filter(
                BankTransaction.erpnext_id == erpnext_id
            ).first()

            # Map status
            status_str = (txn_data.get("status", "") or "").lower()
            status_map = {
                "pending": BankTransactionStatus.PENDING,
                "settled": BankTransactionStatus.SETTLED,
                "unreconciled": BankTransactionStatus.UNRECONCILED,
                "reconciled": BankTransactionStatus.RECONCILED,
                "cancelled": BankTransactionStatus.CANCELLED,
            }
            status = status_map.get(status_str, BankTransactionStatus.PENDING)

            # Link bank account
            bank_account_erpnext = txn_data.get("bank_account")
            bank_account_id = bank_accounts_by_erpnext_id.get(bank_account_erpnext)

            if existing:
                existing.bank_account_id = bank_account_id
                existing.bank_account = bank_account_erpnext
                existing.status = status
                existing.deposit = Decimal(str(txn_data.get("deposit", 0) or 0))
                existing.withdrawal = Decimal(str(txn_data.get("withdrawal", 0) or 0))
                existing.currency = txn_data.get("currency", "NGN")
                existing.description = txn_data.get("description")
                existing.reference_number = txn_data.get("reference_number")
                existing.transaction_id = txn_data.get("transaction_id")
                existing.party_type = txn_data.get("party_type")
                existing.party = txn_data.get("party")
                existing.unallocated_amount = Decimal(str(txn_data.get("unallocated_amount", 0) or 0))
                existing.allocated_amount = Decimal(str(txn_data.get("allocated_amount", 0) or 0))
                existing.docstatus = txn_data.get("docstatus", 0)
                existing.last_synced_at = datetime.utcnow()

                if txn_data.get("date"):
                    try:
                        existing.date = datetime.fromisoformat(txn_data["date"])
                    except (ValueError, TypeError):
                        pass

                sync_client.increment_updated()
            else:
                bank_txn = BankTransaction(
                    erpnext_id=erpnext_id,
                    bank_account_id=bank_account_id,
                    bank_account=bank_account_erpnext,
                    status=status,
                    deposit=float(txn_data.get("deposit", 0) or 0),
                    withdrawal=float(txn_data.get("withdrawal", 0) or 0),
                    currency=txn_data.get("currency", "NGN"),
                    description=txn_data.get("description"),
                    reference_number=txn_data.get("reference_number"),
                    transaction_id=txn_data.get("transaction_id"),
                    party_type=txn_data.get("party_type"),
                    party=txn_data.get("party"),
                    unallocated_amount=float(txn_data.get("unallocated_amount", 0) or 0),
                    allocated_amount=float(txn_data.get("allocated_amount", 0) or 0),
                    docstatus=txn_data.get("docstatus", 0),
                )

                if txn_data.get("date"):
                    try:
                        bank_txn.date = datetime.fromisoformat(txn_data["date"])
                    except (ValueError, TypeError):
                        pass

                sync_client.db.add(bank_txn)
                sync_client.increment_created()

            # Batch commit
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("bank_transactions_batch_committed", processed=i, total=len(transactions))

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_suppliers(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync suppliers/vendors from ERPNext."""
    sync_client.start_sync("suppliers", "full" if full_sync else "incremental")

    try:
        suppliers = await sync_client._fetch_all_doctype(
            client,
            "Supplier",
            fields=["*"],
        )

        for sup_data in suppliers:
            erpnext_id = sup_data.get("name")
            existing = sync_client.db.query(Supplier).filter(
                Supplier.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.supplier_name = sup_data.get("supplier_name", "")
                existing.supplier_group = sup_data.get("supplier_group")
                existing.supplier_type = sup_data.get("supplier_type")
                existing.country = sup_data.get("country")
                existing.default_currency = sup_data.get("default_currency") or "NGN"
                existing.default_bank_account = sup_data.get("default_bank_account")
                existing.tax_id = sup_data.get("tax_id")
                existing.tax_withholding_category = sup_data.get("tax_withholding_category")
                existing.supplier_primary_contact = sup_data.get("supplier_primary_contact")
                existing.supplier_primary_address = sup_data.get("supplier_primary_address")
                existing.email_id = sup_data.get("email_id")
                existing.mobile_no = sup_data.get("mobile_no")
                existing.default_price_list = sup_data.get("default_price_list")
                existing.payment_terms = sup_data.get("payment_terms")
                existing.is_transporter = sup_data.get("is_transporter", 0) == 1
                existing.is_internal_supplier = sup_data.get("is_internal_supplier", 0) == 1
                existing.disabled = sup_data.get("disabled", 0) == 1
                existing.is_frozen = sup_data.get("is_frozen", 0) == 1
                existing.on_hold = sup_data.get("on_hold", 0) == 1
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                supplier = Supplier(
                    erpnext_id=erpnext_id,
                    supplier_name=sup_data.get("supplier_name", ""),
                    supplier_group=sup_data.get("supplier_group"),
                    supplier_type=sup_data.get("supplier_type"),
                    country=sup_data.get("country"),
                    default_currency=sup_data.get("default_currency") or "NGN",
                    default_bank_account=sup_data.get("default_bank_account"),
                    tax_id=sup_data.get("tax_id"),
                    tax_withholding_category=sup_data.get("tax_withholding_category"),
                    supplier_primary_contact=sup_data.get("supplier_primary_contact"),
                    supplier_primary_address=sup_data.get("supplier_primary_address"),
                    email_id=sup_data.get("email_id"),
                    mobile_no=sup_data.get("mobile_no"),
                    default_price_list=sup_data.get("default_price_list"),
                    payment_terms=sup_data.get("payment_terms"),
                    is_transporter=sup_data.get("is_transporter", 0) == 1,
                    is_internal_supplier=sup_data.get("is_internal_supplier", 0) == 1,
                    disabled=sup_data.get("disabled", 0) == 1,
                    is_frozen=sup_data.get("is_frozen", 0) == 1,
                    on_hold=sup_data.get("on_hold", 0) == 1,
                )
                sync_client.db.add(supplier)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_modes_of_payment(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync payment modes from ERPNext (Cash, Bank Transfer, etc.)."""
    sync_client.start_sync("modes_of_payment", "full" if full_sync else "incremental")

    try:
        modes = await sync_client._fetch_all_doctype(
            client,
            "Mode of Payment",
            fields=["*"],
        )

        for mode_data in modes:
            erpnext_id = mode_data.get("name")
            existing = sync_client.db.query(ModeOfPayment).filter(
                ModeOfPayment.erpnext_id == erpnext_id
            ).first()

            # Map type
            type_str = (mode_data.get("type", "") or "").lower()
            type_map = {
                "cash": PaymentModeType.CASH,
                "bank": PaymentModeType.BANK,
                "general": PaymentModeType.GENERAL,
            }
            payment_type = type_map.get(type_str, PaymentModeType.GENERAL)

            if existing:
                existing.mode_of_payment = str(mode_data.get("mode_of_payment") or erpnext_id)
                existing.type = payment_type
                existing.enabled = mode_data.get("enabled", 1) == 1
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                mode = ModeOfPayment(
                    erpnext_id=erpnext_id,
                    mode_of_payment=mode_data.get("mode_of_payment") or str(erpnext_id or ""),
                    type=payment_type,
                    enabled=mode_data.get("enabled", 1) == 1,
                )
                sync_client.db.add(mode)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_cost_centers(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync cost centers from ERPNext for departmental accounting."""
    sync_client.start_sync("cost_centers", "full" if full_sync else "incremental")

    try:
        cost_centers = await sync_client._fetch_all_doctype(
            client,
            "Cost Center",
            fields=["*"],
        )

        for cc_data in cost_centers:
            erpnext_id = cc_data.get("name")
            existing = sync_client.db.query(CostCenter).filter(
                CostCenter.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.cost_center_name = cc_data.get("cost_center_name", "")
                existing.cost_center_number = cc_data.get("cost_center_number")
                existing.parent_cost_center = cc_data.get("parent_cost_center")
                existing.company = cc_data.get("company")
                existing.is_group = cc_data.get("is_group", 0) == 1
                existing.disabled = cc_data.get("disabled", 0) == 1
                existing.lft = cc_data.get("lft")
                existing.rgt = cc_data.get("rgt")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                cost_center = CostCenter(
                    erpnext_id=erpnext_id,
                    cost_center_name=cc_data.get("cost_center_name", ""),
                    cost_center_number=cc_data.get("cost_center_number"),
                    parent_cost_center=cc_data.get("parent_cost_center"),
                    company=cc_data.get("company"),
                    is_group=cc_data.get("is_group", 0) == 1,
                    disabled=cc_data.get("disabled", 0) == 1,
                    lft=cc_data.get("lft"),
                    rgt=cc_data.get("rgt"),
                )
                sync_client.db.add(cost_center)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_fiscal_years(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync fiscal years from ERPNext for accounting periods."""
    sync_client.start_sync("fiscal_years", "full" if full_sync else "incremental")

    try:
        fiscal_years = await sync_client._fetch_all_doctype(
            client,
            "Fiscal Year",
            fields=["*"],
        )

        for fy_data in fiscal_years:
            erpnext_id = fy_data.get("name")
            existing = sync_client.db.query(FiscalYear).filter(
                FiscalYear.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.year = str(fy_data.get("year") or erpnext_id)
                existing.is_short_year = fy_data.get("is_short_year", 0) == 1
                existing.disabled = fy_data.get("disabled", 0) == 1
                existing.auto_created = fy_data.get("auto_created", 0) == 1
                existing.last_synced_at = datetime.utcnow()

                if fy_data.get("year_start_date"):
                    try:
                        existing.year_start_date = datetime.fromisoformat(fy_data["year_start_date"]).date()
                    except (ValueError, TypeError):
                        pass

                if fy_data.get("year_end_date"):
                    try:
                        existing.year_end_date = datetime.fromisoformat(fy_data["year_end_date"]).date()
                    except (ValueError, TypeError):
                        pass

                sync_client.increment_updated()
            else:
                fiscal_year = FiscalYear(
                    erpnext_id=erpnext_id,
                    year=fy_data.get("year") or str(erpnext_id or ""),
                    is_short_year=fy_data.get("is_short_year", 0) == 1,
                    disabled=fy_data.get("disabled", 0) == 1,
                    auto_created=fy_data.get("auto_created", 0) == 1,
                )

                if fy_data.get("year_start_date"):
                    try:
                        fiscal_year.year_start_date = datetime.fromisoformat(fy_data["year_start_date"]).date()
                    except (ValueError, TypeError):
                        pass

                if fy_data.get("year_end_date"):
                    try:
                        fiscal_year.year_end_date = datetime.fromisoformat(fy_data["year_end_date"]).date()
                    except (ValueError, TypeError):
                        pass

                sync_client.db.add(fiscal_year)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_invoices(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync sales invoices from ERPNext."""
    sync_client.start_sync("invoices", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("invoices", full_sync)
        invoices = await sync_client._fetch_all_doctype(
            client,
            "Sales Invoice",
            fields=[
                "name", "customer", "posting_date", "due_date",
                "grand_total", "outstanding_amount", "status",
                "paid_amount", "currency",
                "custom_splynx_invoice_id",
            ],
            filters=filters,
        )

        # Track invoice IDs already assigned an erpnext_id in this transaction
        assigned_invoice_ids: set[int] = set()
        # Track erpnext_ids already processed in this transaction
        processed_erpnext_ids: set[str] = set()

        for inv_data in invoices:
            erpnext_id = inv_data.get("name")

            # Skip if no erpnext_id or already processed in this batch
            if not erpnext_id or erpnext_id in processed_erpnext_ids:
                continue
            processed_erpnext_ids.add(str(erpnext_id))
            custom_splynx_invoice_id = sync_client._safe_int(inv_data.get("custom_splynx_invoice_id"))
            splynx_invoice = (
                sync_client.db.query(Invoice)
                .filter(Invoice.splynx_id == custom_splynx_invoice_id)
                .first()
                if custom_splynx_invoice_id
                else None
            )

            existing_erpnext = sync_client.db.query(Invoice).filter(
                Invoice.erpnext_id == erpnext_id
            ).first()

            # Find customer
            customer_erpnext_id = inv_data.get("customer")
            customer = sync_client.db.query(Customer).filter(
                Customer.erpnext_id == customer_erpnext_id
            ).first()
            customer_id = customer.id if customer else None

            # Map status
            status_str = (inv_data.get("status", "") or "").lower()
            status_map = {
                "paid": InvoiceStatus.PAID,
                "unpaid": InvoiceStatus.PENDING,
                "overdue": InvoiceStatus.OVERDUE,
                "partly paid": InvoiceStatus.PARTIALLY_PAID,
                "cancelled": InvoiceStatus.CANCELLED,
                "return": InvoiceStatus.REFUNDED,
            }
            status = status_map.get(status_str, InvoiceStatus.PENDING)

            total_amount = float(inv_data.get("grand_total", 0) or 0)
            outstanding = float(inv_data.get("outstanding_amount", 0) or 0)
            paid_amount = float(inv_data.get("paid_amount", 0) or 0)

            # Determine target invoice, handling conflicts between splynx linkage and existing erpnext record
            target_invoice: Optional[Invoice] = None
            duplicate_invoice: Optional[Invoice] = None

            if splynx_invoice and existing_erpnext:
                if splynx_invoice.id == existing_erpnext.id:
                    # Same invoice - use it
                    target_invoice = splynx_invoice
                elif existing_erpnext.source == InvoiceSource.ERPNEXT:
                    # Existing ERPNext-only record can be merged into Splynx record
                    target_invoice = splynx_invoice
                    duplicate_invoice = existing_erpnext
                else:
                    # Conflict: existing_erpnext is a Splynx invoice with this erpnext_id
                    # This is a data integrity issue - use existing_erpnext to avoid unique constraint violation
                    logger.warning(
                        "erpnext_splynx_linkage_conflict",
                        erpnext_id=erpnext_id,
                        custom_splynx_id=custom_splynx_invoice_id,
                        existing_invoice_id=existing_erpnext.id,
                        linked_splynx_invoice_id=splynx_invoice.id,
                    )
                    target_invoice = existing_erpnext
            elif splynx_invoice:
                target_invoice = splynx_invoice
            elif existing_erpnext:
                target_invoice = existing_erpnext

            # Fallback soft match if the custom field is missing
            if not target_invoice:
                posting_dt = sync_client._parse_iso_date(inv_data.get("posting_date"))
                if posting_dt and customer_id:
                    # Exclude invoices already assigned in this transaction or already having an erpnext_id
                    target_invoice = (
                        sync_client.db.query(Invoice)
                        .filter(
                            Invoice.source == InvoiceSource.SPLYNX,
                            Invoice.customer_id == customer_id,
                            Invoice.total_amount == Decimal(str(total_amount)),
                            func.date(Invoice.invoice_date) == posting_dt.date(),
                            Invoice.erpnext_id.is_(None),
                            ~Invoice.id.in_(assigned_invoice_ids) if assigned_invoice_ids else Invoice.id.isnot(None),
                        )
                        .first()
                    )

            if target_invoice:
                # Track this invoice as assigned to avoid duplicate erpnext_id assignments
                assigned_invoice_ids.add(target_invoice.id)

                # If we're merging with a duplicate, clear its erpnext_id first to avoid constraint violation
                if duplicate_invoice:
                    duplicate_invoice.erpnext_id = None
                    sync_client.db.flush()  # Flush the NULL assignment before setting the new value

                target_invoice.erpnext_id = erpnext_id
                target_invoice.customer_id = customer_id
                target_invoice.total_amount = Decimal(str(total_amount))
                target_invoice.amount = Decimal(str(total_amount))
                target_invoice.amount_paid = Decimal(str(paid_amount))
                target_invoice.balance = Decimal(str(outstanding))
                target_invoice.status = status
                target_invoice.currency = inv_data.get("currency", "NGN")
                target_invoice.last_synced_at = datetime.utcnow()

                posting_dt = sync_client._parse_iso_date(inv_data.get("posting_date"))
                if posting_dt:
                    target_invoice.invoice_date = posting_dt

                due_dt = sync_client._parse_iso_date(inv_data.get("due_date"))
                if due_dt:
                    target_invoice.due_date = due_dt

                # If we found a duplicate ERPNext-only record, re-home children and delete it
                if duplicate_invoice:
                    for payment in list(duplicate_invoice.payments):
                        payment.invoice_id = target_invoice.id
                    for credit_note in list(duplicate_invoice.credit_notes):
                        credit_note.invoice_id = target_invoice.id
                    sync_client.db.delete(duplicate_invoice)
                sync_client.increment_updated()
            else:
                invoice = Invoice(
                    erpnext_id=erpnext_id,
                    source=InvoiceSource.ERPNEXT,
                    customer_id=customer_id,
                    invoice_number=erpnext_id,
                    total_amount=total_amount,
                    amount=total_amount,
                    amount_paid=paid_amount,
                    balance=outstanding,
                    status=status,
                    currency=inv_data.get("currency", "NGN"),
                    invoice_date=datetime.utcnow(),
                )

                posting_dt = sync_client._parse_iso_date(inv_data.get("posting_date"))
                if posting_dt:
                    invoice.invoice_date = posting_dt

                due_dt = sync_client._parse_iso_date(inv_data.get("due_date"))
                if due_dt:
                    invoice.due_date = due_dt

                sync_client.db.add(invoice)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client._update_sync_cursor("invoices", invoices, len(invoices))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_payments(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync payment entries from ERPNext."""
    sync_client.start_sync("payments", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("payments", full_sync)
        payments = await sync_client._fetch_all_doctype(
            client,
            "Payment Entry",
            fields=[
                "name", "party", "party_type", "posting_date",
                "paid_amount", "mode_of_payment", "reference_no",
                "payment_type", "status",
                "custom_splynx_payment_id",
                "custom_splynx_credit_note_id",
            ],
            filters=filters,
        )

        # Track payment IDs already assigned an erpnext_id in this transaction
        assigned_payment_ids: set[int] = set()
        # Track erpnext_ids already processed in this transaction
        processed_payment_erpnext_ids: set[str] = set()

        for pay_data in payments:
            # Only process customer payments
            if pay_data.get("party_type") != "Customer":
                continue

            erpnext_id = pay_data.get("name")

            # Skip if no erpnext_id or already processed in this batch
            if not erpnext_id or erpnext_id in processed_payment_erpnext_ids:
                continue
            processed_payment_erpnext_ids.add(str(erpnext_id))
            custom_splynx_payment_id = sync_client._safe_int(pay_data.get("custom_splynx_payment_id"))
            splynx_payment = (
                sync_client.db.query(Payment)
                .filter(Payment.splynx_id == custom_splynx_payment_id)
                .first()
                if custom_splynx_payment_id
                else None
            )

            existing_erpnext = sync_client.db.query(Payment).filter(
                Payment.erpnext_id == erpnext_id
            ).first()

            # Find customer
            customer_erpnext_id = pay_data.get("party")
            customer = sync_client.db.query(Customer).filter(
                Customer.erpnext_id == customer_erpnext_id
            ).first()
            customer_id = customer.id if customer else None

            amount = float(pay_data.get("paid_amount", 0) or 0)

            # Map payment method
            mode = (pay_data.get("mode_of_payment", "") or "").lower()
            method_map = {
                "cash": PaymentMethod.CASH,
                "bank transfer": PaymentMethod.BANK_TRANSFER,
                "credit card": PaymentMethod.CARD,
                "debit card": PaymentMethod.CARD,
            }
            payment_method = PaymentMethod.OTHER
            for key, value in method_map.items():
                if key in mode:
                    payment_method = value
                    break

            # Determine target payment, handling conflicts between splynx linkage and existing erpnext record
            target_payment: Optional[Payment] = None
            duplicate_payment: Optional[Payment] = None

            if splynx_payment and existing_erpnext:
                if splynx_payment.id == existing_erpnext.id:
                    # Same payment - use it
                    target_payment = splynx_payment
                elif existing_erpnext.source == PaymentSource.ERPNEXT:
                    # Existing ERPNext-only record can be merged into Splynx record
                    target_payment = splynx_payment
                    duplicate_payment = existing_erpnext
                else:
                    # Conflict: existing_erpnext is a Splynx payment with this erpnext_id
                    # Use existing_erpnext to avoid unique constraint violation
                    logger.warning(
                        "erpnext_splynx_payment_linkage_conflict",
                        erpnext_id=erpnext_id,
                        custom_splynx_id=custom_splynx_payment_id,
                        existing_payment_id=existing_erpnext.id,
                        linked_splynx_payment_id=splynx_payment.id,
                    )
                    target_payment = existing_erpnext
            elif splynx_payment:
                target_payment = splynx_payment
            elif existing_erpnext:
                target_payment = existing_erpnext

            # Soft-match if custom link missing: same amount, customer, and date
            if not target_payment:
                posting_dt = sync_client._parse_iso_date(pay_data.get("posting_date"))
                if posting_dt and customer_id:
                    # Exclude payments already assigned in this transaction or already having an erpnext_id
                    target_payment = (
                        sync_client.db.query(Payment)
                        .filter(
                            Payment.source == PaymentSource.SPLYNX,
                            Payment.customer_id == customer_id,
                            Payment.amount == Decimal(str(amount)),
                            func.date(Payment.payment_date) == posting_dt.date(),
                            Payment.erpnext_id.is_(None),
                            ~Payment.id.in_(assigned_payment_ids) if assigned_payment_ids else Payment.id.isnot(None),
                        )
                        .first()
                    )

            if target_payment:
                # Track this payment as assigned to avoid duplicate erpnext_id assignments
                assigned_payment_ids.add(target_payment.id)

                # If we're merging with a duplicate, clear its erpnext_id first to avoid constraint violation
                if duplicate_payment:
                    duplicate_payment.erpnext_id = None
                    sync_client.db.flush()  # Flush the NULL assignment before setting the new value

                target_payment.erpnext_id = erpnext_id
                target_payment.customer_id = customer_id
                target_payment.amount = Decimal(str(amount))
                target_payment.payment_method = payment_method
                target_payment.transaction_reference = pay_data.get("reference_no")
                target_payment.last_synced_at = datetime.utcnow()

                posting_dt = sync_client._parse_iso_date(pay_data.get("posting_date"))
                if posting_dt:
                    target_payment.payment_date = posting_dt

                # Map ERPNext status to our enum if present
                status_str = (pay_data.get("status", "") or "").lower()
                status_map = {
                    "submitted": PaymentStatus.COMPLETED,
                    "completed": PaymentStatus.COMPLETED,
                    "draft": PaymentStatus.PENDING,
                    "cancelled": PaymentStatus.FAILED,
                    "failed": PaymentStatus.FAILED,
                }
                if status_str in status_map:
                    target_payment.status = status_map[status_str]

                # Delete the duplicate ERPNext-only payment after merging
                if duplicate_payment:
                    sync_client.db.delete(duplicate_payment)

                sync_client.increment_updated()
            else:
                payment = Payment(
                    erpnext_id=erpnext_id,
                    source=PaymentSource.ERPNEXT,
                    customer_id=customer_id,
                    amount=amount,
                    payment_method=payment_method,
                    receipt_number=erpnext_id,
                    transaction_reference=pay_data.get("reference_no"),
                    payment_date=datetime.utcnow(),
                )

                posting_dt = sync_client._parse_iso_date(pay_data.get("posting_date"))
                if posting_dt:
                    payment.payment_date = posting_dt

                sync_client.db.add(payment)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client._update_sync_cursor("payments", payments, len(payments))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_expenses(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync Expense Claims from ERPNext with full fields and FK relationships."""
    sync_client.start_sync("expenses", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("expenses", full_sync)
        # Fetch all expense claims with full fields
        expense_claims = await sync_client._fetch_all_doctype(
            client,
            "Expense Claim",
            fields=["*"],
            filters=filters,
        )

        # Pre-fetch employees by erpnext_id for FK linking
        employees_by_erpnext_id = {
            e.erpnext_id: e.id
            for e in sync_client.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).all()
        }

        # Pre-fetch projects by erpnext_id for FK linking
        projects_by_erpnext_id = {
            p.erpnext_id: p.id
            for p in sync_client.db.query(Project).filter(Project.erpnext_id.isnot(None)).all()
        }

        # Skipping Expense Claim Detail prefetch to avoid 403 permission errors on that doctype.
        expense_details: Dict[str, List[Dict[str, Any]]] = {}
        logger.info("expense_details_prefetch_skipped", reason="disabled to avoid permission errors")

        # Helper for Decimal conversion
        def to_decimal(val: Any) -> Decimal:
            return Decimal(str(val or 0))

        batch_size = 500
        for i, exp_data in enumerate(expense_claims, 1):
            erpnext_id = exp_data.get("name")
            existing = sync_client.db.query(Expense).filter(Expense.erpnext_id == erpnext_id).first()

            # Map status
            status_str = (exp_data.get("status", "") or "").lower()
            status_map = {
                "draft": ExpenseStatus.DRAFT,
                "pending approval": ExpenseStatus.PENDING,
                "approved": ExpenseStatus.APPROVED,
                "rejected": ExpenseStatus.REJECTED,
                "paid": ExpenseStatus.PAID,
                "cancelled": ExpenseStatus.CANCELLED,
                "unpaid": ExpenseStatus.APPROVED,  # Approved but not yet paid
            }
            status = status_map.get(status_str, ExpenseStatus.DRAFT)

            # Link to employee
            erpnext_employee = exp_data.get("employee")
            employee_id = employees_by_erpnext_id.get(erpnext_employee) if erpnext_employee else None

            # Link to project
            erpnext_project = exp_data.get("project")
            project_id = projects_by_erpnext_id.get(erpnext_project) if erpnext_project else None

            # Get expense_type and description from pre-fetched child records (N+1 fix)
            expense_type = None
            description = None
            claim_details = expense_details.get(str(erpnext_id), []) if erpnext_id else []
            if claim_details:
                # Get expense types, join if multiple
                expense_types = [d.get("expense_type") for d in claim_details if d.get("expense_type")]
                expense_type = ", ".join(sorted(set(str(t) for t in expense_types if t))) if expense_types else None
                # Get descriptions
                descriptions = [d.get("description") for d in claim_details if d.get("description")]
                description = "; ".join([str(desc) for desc in descriptions]) if descriptions else None

            if existing:
                # Employee
                existing.employee_id = employee_id
                existing.employee_name = exp_data.get("employee_name")
                existing.erpnext_employee = erpnext_employee

                # Project
                existing.project_id = project_id
                existing.erpnext_project = erpnext_project

                # Expense details
                existing.expense_type = expense_type
                existing.description = description
                existing.remark = exp_data.get("remark")

                # Amounts
                existing.total_claimed_amount = to_decimal(exp_data.get("total_claimed_amount"))
                existing.total_sanctioned_amount = to_decimal(exp_data.get("total_sanctioned_amount"))
                existing.total_amount_reimbursed = to_decimal(exp_data.get("total_amount_reimbursed"))
                existing.total_advance_amount = to_decimal(exp_data.get("total_advance_amount"))
                existing.amount = to_decimal(exp_data.get("total_claimed_amount"))

                # Taxes
                existing.total_taxes_and_charges = to_decimal(exp_data.get("total_taxes_and_charges"))

                # Categorization
                existing.cost_center = exp_data.get("cost_center")
                existing.company = exp_data.get("company")

                # Accounting
                existing.payable_account = exp_data.get("payable_account")
                existing.mode_of_payment = exp_data.get("mode_of_payment")

                # Approval
                existing.approval_status = exp_data.get("approval_status")
                existing.expense_approver = exp_data.get("expense_approver")

                # Status
                existing.status = status
                existing.is_paid = exp_data.get("is_paid", 0) == 1
                existing.docstatus = exp_data.get("docstatus", 0)

                # Task
                existing.erpnext_task = exp_data.get("task")

                existing.last_synced_at = datetime.utcnow()

                # Dates
                if exp_data.get("posting_date"):
                    try:
                        existing.posting_date = datetime.fromisoformat(exp_data["posting_date"])
                        existing.expense_date = existing.posting_date
                    except (ValueError, TypeError):
                        pass

                if exp_data.get("clearance_date"):
                    try:
                        existing.clearance_date = datetime.fromisoformat(exp_data["clearance_date"])
                    except (ValueError, TypeError):
                        pass

                sync_client.increment_updated()
            else:
                expense = Expense(
                    erpnext_id=erpnext_id,

                    # Employee
                    employee_id=employee_id,
                    employee_name=exp_data.get("employee_name"),
                    erpnext_employee=erpnext_employee,

                    # Project
                    project_id=project_id,
                    erpnext_project=erpnext_project,

                    # Expense details
                    expense_type=expense_type,
                    description=description,
                    remark=exp_data.get("remark"),

                    # Amounts
                    total_claimed_amount=to_decimal(exp_data.get("total_claimed_amount")),
                    total_sanctioned_amount=to_decimal(exp_data.get("total_sanctioned_amount")),
                    total_amount_reimbursed=to_decimal(exp_data.get("total_amount_reimbursed")),
                    total_advance_amount=to_decimal(exp_data.get("total_advance_amount")),
                    amount=to_decimal(exp_data.get("total_claimed_amount")),

                    # Taxes
                    total_taxes_and_charges=to_decimal(exp_data.get("total_taxes_and_charges")),

                    # Categorization
                    cost_center=exp_data.get("cost_center"),
                    company=exp_data.get("company"),

                    # Accounting
                    payable_account=exp_data.get("payable_account"),
                    mode_of_payment=exp_data.get("mode_of_payment"),

                    # Approval
                    approval_status=exp_data.get("approval_status"),
                    expense_approver=exp_data.get("expense_approver"),

                    # Status
                    status=status,
                    is_paid=exp_data.get("is_paid", 0) == 1,
                    docstatus=exp_data.get("docstatus", 0),

                    # Task
                    erpnext_task=exp_data.get("task"),
                )

                # Dates
                if exp_data.get("posting_date"):
                    try:
                        expense.posting_date = datetime.fromisoformat(exp_data["posting_date"])
                        expense.expense_date = expense.posting_date
                    except (ValueError, TypeError):
                        expense.expense_date = datetime.utcnow()
                else:
                    expense.expense_date = datetime.utcnow()

                if exp_data.get("clearance_date"):
                    try:
                        expense.clearance_date = datetime.fromisoformat(exp_data["clearance_date"])
                    except (ValueError, TypeError):
                        pass

                sync_client.db.add(expense)
                sync_client.increment_created()

            # Batch commit
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("expenses_batch_committed", processed=i, total=len(expense_claims))

        sync_client.db.commit()
        sync_client._update_sync_cursor("expenses", expense_claims, len(expense_claims))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
