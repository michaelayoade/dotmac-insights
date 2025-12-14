"""Document Posting service for posting documents to the GL."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalEntryType, GLEntry
from app.models.accounting_ext import FiscalPeriod, FiscalPeriodStatus
from app.models.invoice import Invoice
from app.models.accounting import PurchaseInvoice
from app.models.payment import Payment
from app.models.supplier_payment import SupplierPayment
from app.models.credit_note import CreditNote
from app.models.books_settings import DebitNote


class PostingError(Exception):
    """Error during document posting."""
    pass


class DocumentPostingService:
    """
    Service for posting documents to the General Ledger.

    Creates journal entries and GL entries for:
    - Invoices (AR)
    - Bills (AP)
    - Payments (AR and AP)
    - Credit notes
    - Debit notes
    """

    def __init__(self, db: Session):
        self.db = db

    def post_invoice(
        self,
        invoice_id: int,
        user_id: int,
        posting_date: Optional[datetime] = None,
    ) -> JournalEntry:
        """
        Post an invoice to the GL.

        Creates:
        - Debit: Accounts Receivable
        - Credit: Revenue account(s)
        - Credit: Tax Payable (if applicable)

        Args:
            invoice_id: ID of the invoice to post
            user_id: ID of user posting
            posting_date: Override posting date

        Returns:
            Created JournalEntry
        """
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise PostingError("Invoice not found")

        if invoice.docstatus == 1:
            raise PostingError("Invoice is already posted")

        posting_dt = posting_date or invoice.invoice_date
        self._validate_fiscal_period(posting_dt)

        # Build GL entries
        entries = []

        # Debit AR
        entries.append({
            "account": self._get_ar_account(invoice),
            "party_type": "Customer",
            "party": str(invoice.customer_id),
            "debit": invoice.total_amount,
            "credit": Decimal("0"),
        })

        # Credit Revenue (net amount)
        entries.append({
            "account": self._get_revenue_account(invoice),
            "debit": Decimal("0"),
            "credit": invoice.amount,
        })

        # Credit Tax Payable (if tax)
        if invoice.tax_amount and invoice.tax_amount > 0:
            entries.append({
                "account": self._get_tax_liability_account(),
                "debit": Decimal("0"),
                "credit": invoice.tax_amount,
            })

        # Create journal entry
        je = self._create_journal_entry(
            voucher_type=JournalEntryType.JOURNAL_ENTRY,
            posting_date=posting_dt,
            entries=entries,
            user_remark=f"Invoice {invoice.invoice_number}",
            company=invoice.company,
        )

        # Update invoice
        invoice.docstatus = 1
        invoice.journal_entry_id = je.id
        invoice.workflow_status = "posted"

        return je

    def post_bill(
        self,
        bill_id: int,
        user_id: int,
        posting_date: Optional[datetime] = None,
    ) -> JournalEntry:
        """
        Post a bill (purchase invoice) to the GL.

        Creates:
        - Credit: Accounts Payable
        - Debit: Expense/Asset account(s)
        - Debit: Tax Receivable (if applicable)

        Args:
            bill_id: ID of the bill to post
            user_id: ID of user posting
            posting_date: Override posting date

        Returns:
            Created JournalEntry
        """
        bill = self.db.query(PurchaseInvoice).filter(PurchaseInvoice.id == bill_id).first()
        if not bill:
            raise PostingError("Bill not found")

        if bill.docstatus == 1:
            raise PostingError("Bill is already posted")

        posting_dt = posting_date or bill.posting_date
        self._validate_fiscal_period(posting_dt)

        entries = []

        # Credit AP
        entries.append({
            "account": self._get_ap_account(bill),
            "party_type": "Supplier",
            "party": bill.supplier,
            "debit": Decimal("0"),
            "credit": bill.grand_total,
        })

        # Debit Expense (net amount)
        net_amount = bill.grand_total - (bill.tax_amount or Decimal("0"))
        entries.append({
            "account": self._get_expense_account(bill),
            "debit": net_amount,
            "credit": Decimal("0"),
        })

        # Debit Tax Receivable (if tax)
        if bill.tax_amount and bill.tax_amount > 0:
            entries.append({
                "account": self._get_tax_asset_account(),
                "debit": bill.tax_amount,
                "credit": Decimal("0"),
            })

        je = self._create_journal_entry(
            voucher_type=JournalEntryType.JOURNAL_ENTRY,
            posting_date=posting_dt,
            entries=entries,
            user_remark=f"Bill {bill.erpnext_id or bill.bill_number}",
            company=bill.company,
        )

        bill.docstatus = 1
        bill.journal_entry_id = je.id
        bill.workflow_status = "posted"

        return je

    def post_payment(
        self,
        payment_id: int,
        user_id: int,
        posting_date: Optional[datetime] = None,
    ) -> JournalEntry:
        """
        Post a customer payment to the GL.

        Creates:
        - Debit: Bank/Cash account
        - Credit: Accounts Receivable

        Args:
            payment_id: ID of the payment to post
            user_id: ID of user posting
            posting_date: Override posting date

        Returns:
            Created JournalEntry
        """
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise PostingError("Payment not found")

        if payment.docstatus == 1:
            raise PostingError("Payment is already posted")

        posting_dt = posting_date or payment.payment_date
        self._validate_fiscal_period(posting_dt)

        entries = []

        # Debit Bank
        entries.append({
            "account": self._get_bank_account(payment),
            "debit": payment.amount,
            "credit": Decimal("0"),
        })

        # Credit AR
        entries.append({
            "account": self._get_ar_account(None),
            "party_type": "Customer",
            "party": str(payment.customer_id),
            "debit": Decimal("0"),
            "credit": payment.amount,
        })

        je = self._create_journal_entry(
            voucher_type=JournalEntryType.BANK_ENTRY,
            posting_date=posting_dt,
            entries=entries,
            user_remark=f"Payment {payment.receipt_number}",
            company=None,
        )

        payment.docstatus = 1
        payment.journal_entry_id = je.id
        payment.workflow_status = "posted"

        return je

    def post_supplier_payment(
        self,
        payment_id: int,
        user_id: int,
        posting_date: Optional[datetime] = None,
    ) -> JournalEntry:
        """
        Post a supplier payment to the GL.

        Creates:
        - Credit: Bank/Cash account
        - Debit: Accounts Payable

        Args:
            payment_id: ID of the supplier payment to post
            user_id: ID of user posting
            posting_date: Override posting date

        Returns:
            Created JournalEntry
        """
        payment = self.db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
        if not payment:
            raise PostingError("Supplier payment not found")

        if payment.docstatus == 1:
            raise PostingError("Payment is already posted")

        posting_dt = posting_date or payment.posting_date
        self._validate_fiscal_period(posting_dt)

        entries = []

        # Credit Bank
        entries.append({
            "account": self._get_bank_account_for_supplier(payment),
            "debit": Decimal("0"),
            "credit": payment.paid_amount,
        })

        # Debit AP
        entries.append({
            "account": self._get_ap_account(None),
            "party_type": "Supplier",
            "party": str(payment.supplier_id),
            "debit": payment.paid_amount,
            "credit": Decimal("0"),
        })

        je = self._create_journal_entry(
            voucher_type=JournalEntryType.BANK_ENTRY,
            posting_date=posting_dt,
            entries=entries,
            user_remark=f"Supplier Payment {payment.payment_number}",
            company=payment.company,
        )

        payment.docstatus = 1
        payment.journal_entry_id = je.id
        payment.workflow_status = "posted"

        return je

    def post_credit_note(
        self,
        credit_note_id: int,
        user_id: int,
        posting_date: Optional[datetime] = None,
    ) -> JournalEntry:
        """
        Post a credit note to the GL.

        Creates:
        - Credit: Accounts Receivable
        - Debit: Revenue/Returns account

        Args:
            credit_note_id: ID of the credit note to post
            user_id: ID of user posting
            posting_date: Override posting date

        Returns:
            Created JournalEntry
        """
        cn = self.db.query(CreditNote).filter(CreditNote.id == credit_note_id).first()
        if not cn:
            raise PostingError("Credit note not found")

        if cn.docstatus == 1:
            raise PostingError("Credit note is already posted")

        posting_dt = posting_date or cn.issue_date or cn.posting_date
        self._validate_fiscal_period(posting_dt)

        entries = []

        # Credit AR
        entries.append({
            "account": self._get_ar_account(None),
            "party_type": "Customer",
            "party": str(cn.customer_id),
            "debit": Decimal("0"),
            "credit": cn.amount,
        })

        # Debit Sales Returns
        entries.append({
            "account": self._get_sales_returns_account(),
            "debit": cn.amount,
            "credit": Decimal("0"),
        })

        je = self._create_journal_entry(
            voucher_type=JournalEntryType.CREDIT_NOTE,
            posting_date=posting_dt,
            entries=entries,
            user_remark=f"Credit Note {cn.credit_number}",
            company=cn.company,
        )

        cn.docstatus = 1
        cn.journal_entry_id = je.id
        cn.workflow_status = "posted"

        return je

    def reverse_posting(
        self,
        journal_entry_id: int,
        user_id: int,
        reason: str,
    ) -> JournalEntry:
        """
        Create a reversal entry for a posted journal entry.

        Args:
            journal_entry_id: ID of the journal entry to reverse
            user_id: ID of user reversing
            reason: Reason for reversal

        Returns:
            Reversal JournalEntry
        """
        original = self.db.query(JournalEntry).filter(
            JournalEntry.id == journal_entry_id
        ).first()
        if not original:
            raise PostingError("Journal entry not found")

        if original.docstatus != 1:
            raise PostingError("Can only reverse posted entries")

        # Get original GL entries
        gl_entries = self.db.query(GLEntry).filter(
            GLEntry.voucher_no == original.erpnext_id,
            GLEntry.voucher_type == "Journal Entry",
        ).all()

        # Create reversal entries (swap debits and credits)
        reversal_entries = []
        for gl in gl_entries:
            reversal_entries.append({
                "account": gl.account,
                "party_type": gl.party_type,
                "party": gl.party,
                "debit": gl.credit,  # Swap
                "credit": gl.debit,  # Swap
            })

        je = self._create_journal_entry(
            voucher_type=original.voucher_type,
            posting_date=datetime.utcnow(),
            entries=reversal_entries,
            user_remark=f"Reversal of {original.erpnext_id}: {reason}",
            company=original.company,
        )

        # Mark original as cancelled
        original.docstatus = 2

        return je

    def _create_journal_entry(
        self,
        voucher_type: JournalEntryType,
        posting_date: datetime,
        entries: List[Dict[str, Any]],
        user_remark: Optional[str] = None,
        company: Optional[str] = None,
    ) -> JournalEntry:
        """Create a journal entry with GL entries."""
        # Calculate totals
        total_debit = sum(e.get("debit", Decimal("0")) for e in entries)
        total_credit = sum(e.get("credit", Decimal("0")) for e in entries)

        # Validate balance
        if abs(total_debit - total_credit) > Decimal("0.01"):
            raise PostingError(
                f"Journal entry is not balanced: debit={total_debit}, credit={total_credit}"
            )

        je = JournalEntry(
            voucher_type=voucher_type,
            posting_date=posting_date,
            company=company,
            total_debit=total_debit,
            total_credit=total_credit,
            user_remark=user_remark,
            docstatus=1,  # Posted
        )
        self.db.add(je)
        self.db.flush()

        # Create GL entries
        for entry in entries:
            gl = GLEntry(
                posting_date=posting_date,
                account=entry.get("account"),
                party_type=entry.get("party_type"),
                party=entry.get("party"),
                debit=entry.get("debit", Decimal("0")),
                credit=entry.get("credit", Decimal("0")),
                debit_in_account_currency=entry.get("debit", Decimal("0")),
                credit_in_account_currency=entry.get("credit", Decimal("0")),
                voucher_type="Journal Entry",
                voucher_no=je.erpnext_id,
                cost_center=entry.get("cost_center"),
                company=company,
            )
            self.db.add(gl)

        return je

    def _validate_fiscal_period(self, posting_date: datetime) -> None:
        """Validate that posting date falls within an open fiscal period."""
        period = self.db.query(FiscalPeriod).filter(
            FiscalPeriod.start_date <= posting_date.date(),
            FiscalPeriod.end_date >= posting_date.date(),
        ).first()

        if period and period.status != FiscalPeriodStatus.OPEN:
            raise PostingError(
                f"Fiscal period {period.period_name} is {period.status.value}, not open"
            )

    def _get_ar_account(self, invoice: Optional[Invoice]) -> str:
        """Get the Accounts Receivable account."""
        # TODO: Look up from company settings or customer
        return "Debtors - Company"

    def _get_ap_account(self, bill: Optional[PurchaseInvoice]) -> str:
        """Get the Accounts Payable account."""
        # TODO: Look up from company settings or supplier
        return "Creditors - Company"

    def _get_revenue_account(self, invoice: Invoice) -> str:
        """Get the revenue account for an invoice."""
        # TODO: Look up from line items or invoice category
        return "Sales - Company"

    def _get_expense_account(self, bill: PurchaseInvoice) -> str:
        """Get the expense account for a bill."""
        # TODO: Look up from line items or bill category
        return "Cost of Goods Sold - Company"

    def _get_tax_liability_account(self) -> str:
        """Get the tax liability account (VAT payable)."""
        return "VAT - Company"

    def _get_tax_asset_account(self) -> str:
        """Get the tax asset account (input VAT)."""
        return "Input VAT - Company"

    def _get_bank_account(self, payment: Payment) -> str:
        """Get the bank account for a payment."""
        # TODO: Look up from bank_account_id
        return "Bank - Company"

    def _get_bank_account_for_supplier(self, payment: SupplierPayment) -> str:
        """Get the bank account for a supplier payment."""
        # TODO: Look up from bank_account_id
        return "Bank - Company"

    def _get_sales_returns_account(self) -> str:
        """Get the sales returns account."""
        return "Sales Returns - Company"
