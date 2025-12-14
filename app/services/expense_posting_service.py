"""Posting service for expense claims."""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import List

from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalEntryType, GLEntry
from app.models.expense_management import ExpenseClaim, ExpenseClaimLine, ExpenseClaimStatus, CashAdvanceStatus, CashAdvance
from app.services.document_posting import DocumentPostingService, PostingError


class ExpensePostingService:
    """Creates GL postings for expense claims and handles reversals."""

    def __init__(self, db: Session):
        self.db = db
        self.posting = DocumentPostingService(db)

    def post_claim(
        self,
        claim: ExpenseClaim,
        user_id: int,
        posting_date: date | None = None,
    ) -> JournalEntry:
        """Post an expense claim to the GL."""
        if claim.journal_entry_id:
            raise HTTPException(status_code=400, detail="Claim already posted")
        if claim.status == ExpenseClaimStatus.REVERSED:
            raise HTTPException(status_code=400, detail="Cannot post a reversed claim")

        posting_dt = posting_date or claim.posting_date or claim.claim_date
        posting_ts = datetime.combine(posting_dt, datetime.min.time())
        self.posting._validate_fiscal_period(posting_ts)

        entries: List[dict] = []
        total_credit = Decimal("0")

        for line in claim.lines:
            base_amount = self._to_base(line.claimed_amount, line.conversion_rate)
            base_tax = self._to_base(line.tax_amount, line.conversion_rate)

            expense_account = line.expense_account or getattr(line.category, "expense_account", None) or "Expense - Misc"
            cost_center = line.cost_center or claim.cost_center

            # Debit expense (include tax if not reclaimable)
            debit_amount = base_amount + (base_tax if not line.is_tax_reclaimable else Decimal("0"))
            if debit_amount > 0:
                entries.append(
                    {
                        "account": expense_account,
                        "debit": debit_amount,
                        "credit": Decimal("0"),
                        "cost_center": cost_center,
                        "party_type": None,
                        "party": None,
                    }
                )
                total_credit += debit_amount

            # Debit input tax if reclaimable
            if line.is_tax_reclaimable and base_tax > 0:
                entries.append(
                    {
                        "account": self._tax_input_account(claim),
                        "debit": base_tax,
                        "credit": Decimal("0"),
                        "cost_center": cost_center,
                        "party_type": None,
                        "party": None,
                    }
                )
                total_credit += base_tax

        if total_credit <= 0:
            raise HTTPException(status_code=400, detail="Claim has no amount to post")

        payable_account = claim.payable_account or "Employee Payable - Default"
        payable_amount = total_credit

        # Apply cash advance to reduce payable if linked
        if claim.cash_advance_id and claim.cash_advance_amount > 0:
            advance_applied = min(claim.cash_advance_amount, total_credit)
            advance_account = (
                claim.cash_advance.advance_account
                if claim.cash_advance and claim.cash_advance.advance_account
                else "Employee Advances - Default"
            )
            entries.append(
                {
                    "account": advance_account,
                    "party_type": "Employee",
                    "party": str(claim.employee_id),
                    "debit": Decimal("0"),
                    "credit": advance_applied,
                    "cost_center": claim.cost_center,
                }
            )
            payable_amount -= advance_applied

            # Update cash advance settlement tracking
            if claim.cash_advance:
                ca = claim.cash_advance
                ca.settled_amount = (ca.settled_amount or Decimal("0")) + advance_applied
                ca.outstanding_amount = (ca.disbursed_amount or Decimal("0")) - ca.settled_amount - (ca.refund_amount or Decimal("0"))
                ca.status = CashAdvanceStatus.FULLY_SETTLED if ca.outstanding_amount <= 0 else CashAdvanceStatus.PARTIALLY_SETTLED

        if payable_amount > 0:
            entries.append(
                {
                    "account": payable_account,
                    "party_type": "Employee",
                    "party": str(claim.employee_id),
                    "debit": Decimal("0"),
                    "credit": payable_amount,
                    "cost_center": claim.cost_center,
                }
            )

        je = self._create_journal_entry(
            posting_ts=posting_ts,
            company=claim.company,
            entries=entries,
            remark=f"Expense Claim {claim.claim_number or claim.id}",
            claim_number=claim.claim_number,
        )

        claim.journal_entry_id = je.id
        claim.posted_at = datetime.utcnow()
        claim.posted_by_id = user_id
        claim.status = ExpenseClaimStatus.POSTED
        claim.posting_date = posting_dt

        return je

    def reverse_claim(self, claim: ExpenseClaim, reason: str, user_id: int) -> JournalEntry:
        """Reverse a posted claim by creating an opposite JE."""
        if not claim.journal_entry_id:
            raise HTTPException(status_code=400, detail="Claim is not posted")

        reversal = self.posting.reverse_posting(
            journal_entry_id=claim.journal_entry_id,
            user_id=user_id,
            reason=reason,
        )

        claim.status = ExpenseClaimStatus.REVERSED
        claim.reversal_reason = reason
        claim.reversal_journal_entry_id = reversal.id
        claim.reversed_at = datetime.utcnow()
        claim.reversed_by_id = user_id

        return reversal

    # -------------------------------------------------------------------------
    # Cash Advance Posting
    # -------------------------------------------------------------------------

    def post_cash_advance_disbursement(
        self,
        advance: CashAdvance,
        amount: Decimal,
        user_id: int,
        posting_date: date | None = None,
    ) -> JournalEntry:
        """Disburse a cash advance: Dr Employee Advances, Cr Bank/Cash."""
        posting_dt = posting_date or advance.request_date
        posting_ts = datetime.combine(posting_dt, datetime.min.time())
        self.posting._validate_fiscal_period(posting_ts)

        base_amount = self._to_base(amount, advance.conversion_rate)
        advance_account = advance.advance_account or "Employee Advances - Default"
        bank_account = "Bank - Default"

        entries = [
            {
                "account": advance_account,
                "party_type": "Employee",
                "party": str(advance.employee_id),
                "debit": base_amount,
                "credit": Decimal("0"),
                "cost_center": None,
            },
            {
                "account": bank_account,
                "party_type": None,
                "party": None,
                "debit": Decimal("0"),
                "credit": base_amount,
                "cost_center": None,
            },
        ]

        je = self._create_journal_entry(
            posting_ts=posting_ts,
            company=advance.company,
            entries=entries,
            remark=f"Cash Advance Disbursement {advance.advance_number or advance.id}",
            claim_number=advance.advance_number,
        )

        advance.journal_entry_id = je.id
        return je

    def post_cash_advance_refund(
        self,
        advance: CashAdvance,
        refund_amount: Decimal,
        user_id: int,
        posting_date: date | None = None,
    ) -> JournalEntry:
        """Record refund of unused advance: Dr Bank, Cr Employee Advances."""
        if refund_amount <= 0:
            raise HTTPException(status_code=400, detail="Refund amount must be positive")

        posting_dt = posting_date or advance.request_date
        posting_ts = datetime.combine(posting_dt, datetime.min.time())
        self.posting._validate_fiscal_period(posting_ts)

        base_amount = self._to_base(refund_amount, advance.conversion_rate)
        advance_account = advance.advance_account or "Employee Advances - Default"
        bank_account = "Bank - Default"

        entries = [
            {
                "account": bank_account,
                "party_type": None,
                "party": None,
                "debit": base_amount,
                "credit": Decimal("0"),
                "cost_center": None,
            },
            {
                "account": advance_account,
                "party_type": "Employee",
                "party": str(advance.employee_id),
                "debit": Decimal("0"),
                "credit": base_amount,
                "cost_center": None,
            },
        ]

        je = self._create_journal_entry(
            posting_ts=posting_ts,
            company=advance.company,
            entries=entries,
            remark=f"Cash Advance Refund {advance.advance_number or advance.id}",
            claim_number=advance.advance_number,
        )
        advance.journal_entry_id = je.id
        return je

    def _create_journal_entry(
        self,
        posting_ts: datetime,
        company: str | None,
        entries: List[dict],
        remark: str,
        claim_number: str | None,
    ) -> JournalEntry:
        total_debit = sum(e.get("debit", Decimal("0")) for e in entries)
        total_credit = sum(e.get("credit", Decimal("0")) for e in entries)
        if abs(total_debit - total_credit) > Decimal("0.01"):
            raise PostingError(
                f"Journal entry not balanced: debit={total_debit}, credit={total_credit}"
            )

        je = JournalEntry(
            voucher_type=JournalEntryType.JOURNAL_ENTRY,
            posting_date=posting_ts,
            company=company,
            total_debit=total_debit,
            total_credit=total_credit,
            user_remark=remark,
            docstatus=1,
            erpnext_id=claim_number,
        )
        self.db.add(je)
        self.db.flush()

        voucher_no = je.erpnext_id or str(je.id)

        for entry in entries:
            gl = GLEntry(
                posting_date=posting_ts,
                account=entry.get("account"),
                party_type=entry.get("party_type"),
                party=entry.get("party"),
                debit=entry.get("debit", Decimal("0")),
                credit=entry.get("credit", Decimal("0")),
                debit_in_account_currency=entry.get("debit", Decimal("0")),
                credit_in_account_currency=entry.get("credit", Decimal("0")),
                voucher_type="Journal Entry",
                voucher_no=voucher_no,
                cost_center=entry.get("cost_center"),
                company=company,
            )
            self.db.add(gl)

        return je

    def _tax_input_account(self, claim: ExpenseClaim) -> str:
        return "Input VAT - Default" if not claim.company else f"Input VAT - {claim.company}"

    def _to_base(self, amount: Decimal, rate: Decimal) -> Decimal:
        return (amount or Decimal("0")) * (rate or Decimal("1"))
