from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.database import Base, SessionLocal, engine
from app.models.accounting import (
    BankAccount,
    BankTransaction,
    BankTransactionPayment,
    BankTransactionStatus,
    BankReconciliation,
    BankReconciliationStatus,
    GLEntry,
)
from app.services.bank_reconciliation import BankReconciliationService


@pytest.fixture
def seeded_reconciliation():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        bank_account = BankAccount(
            account_name="Test Bank Pagination",
            company="TestCo",
            currency="NGN",
        )
        db.add(bank_account)
        db.flush()

        reconciliation = BankReconciliation(
            bank_account=bank_account.account_name,
            company=bank_account.company,
            from_date=date(2025, 1, 1),
            to_date=date(2025, 1, 31),
            bank_statement_opening_balance=Decimal("0"),
            bank_statement_closing_balance=Decimal("0"),
            account_opening_balance=Decimal("0"),
            status=BankReconciliationStatus.IN_PROGRESS,
        )
        db.add(reconciliation)
        db.flush()

        base_date = datetime(2025, 1, 2)
        bank_txns = []
        for i in range(3):
            bank_txns.append(BankTransaction(
                date=base_date + timedelta(days=i),
                bank_account=bank_account.account_name,
                company=bank_account.company,
                deposit=Decimal("100") + i,
                withdrawal=Decimal("0"),
                status=BankTransactionStatus.UNRECONCILED,
            ))
        reconciled_txn = BankTransaction(
            date=base_date + timedelta(days=10),
            bank_account=bank_account.account_name,
            company=bank_account.company,
            deposit=Decimal("50"),
            withdrawal=Decimal("0"),
            status=BankTransactionStatus.RECONCILED,
        )
        bank_txns.append(reconciled_txn)

        for txn in bank_txns:
            db.add(txn)
        db.flush()

        gl_entries = [
            GLEntry(
                posting_date=base_date + timedelta(days=1),
                account=bank_account.account_name,
                debit=Decimal("100"),
                credit=Decimal("0"),
                voucher_type="Journal Entry",
                voucher_no="JE-001",
                company=bank_account.company,
            ),
            GLEntry(
                posting_date=base_date + timedelta(days=2),
                account=bank_account.account_name,
                debit=Decimal("200"),
                credit=Decimal("0"),
                voucher_type="Journal Entry",
                voucher_no="JE-002",
                company=bank_account.company,
            ),
            GLEntry(
                posting_date=base_date + timedelta(days=3),
                account=bank_account.account_name,
                debit=Decimal("50"),
                credit=Decimal("0"),
                voucher_type="Journal Entry",
                voucher_no="JE-MATCH",
                company=bank_account.company,
            ),
            GLEntry(
                posting_date=base_date + timedelta(days=4),
                account=bank_account.account_name,
                debit=Decimal("75"),
                credit=Decimal("0"),
                voucher_type="Journal Entry",
                voucher_no="JE-CANCELLED",
                company=bank_account.company,
                is_cancelled=True,
            ),
        ]
        for entry in gl_entries:
            db.add(entry)
        db.flush()

        matched_payment = BankTransactionPayment(
            bank_transaction_id=reconciled_txn.id,
            payment_document="Journal Entry",
            payment_entry="JE-MATCH",
            allocated_amount=Decimal("50"),
        )
        db.add(matched_payment)
        db.commit()

        yield db, reconciliation.id
    finally:
        db.rollback()
        db.query(BankTransactionPayment).filter(
            BankTransactionPayment.payment_entry.in_(["JE-MATCH"])
        ).delete(synchronize_session=False)
        db.query(GLEntry).filter(
            GLEntry.voucher_no.in_(["JE-001", "JE-002", "JE-MATCH", "JE-CANCELLED"])
        ).delete(synchronize_session=False)
        db.query(BankTransaction).filter(
            BankTransaction.bank_account == "Test Bank Pagination"
        ).delete(synchronize_session=False)
        db.query(BankReconciliation).filter(
            BankReconciliation.bank_account == "Test Bank Pagination"
        ).delete(synchronize_session=False)
        db.query(BankAccount).filter(
            BankAccount.account_name == "Test Bank Pagination"
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_reconciliation_outstanding_pagination(seeded_reconciliation):
    db, reconciliation_id = seeded_reconciliation
    service = BankReconciliationService(db)

    result = service.get_outstanding_items(
        reconciliation_id,
        bank_limit=2,
        bank_offset=1,
        gl_limit=1,
        gl_offset=1,
    )

    assert result["summary"]["unmatched_bank_total_count"] == 3
    assert result["summary"]["unmatched_gl_total_count"] == 2
    assert len(result["unmatched_bank_transactions"]) == 2
    assert len(result["unmatched_gl_entries"]) == 1


# =============================================================================
# RECONCILIATION INVARIANT TESTS
# =============================================================================


class TestReconciliationInvariants:
    """Test accounting correctness invariants for bank reconciliation."""

    def test_outstanding_counts_consistent_across_pagination(
        self, seeded_reconciliation
    ):
        """Total counts must remain consistent regardless of pagination offset."""
        db, reconciliation_id = seeded_reconciliation
        service = BankReconciliationService(db)

        # Get full result (no pagination limits)
        full = service.get_outstanding_items(reconciliation_id)

        # Get paginated results - page 1
        page1 = service.get_outstanding_items(
            reconciliation_id, bank_limit=2, bank_offset=0
        )
        # Get paginated results - page 2
        page2 = service.get_outstanding_items(
            reconciliation_id, bank_limit=2, bank_offset=2
        )

        # Total counts must be consistent across all calls
        assert page1["summary"]["unmatched_bank_total_count"] == \
               full["summary"]["unmatched_bank_total_count"], \
               "Page 1 bank total count diverged from full result"
        assert page2["summary"]["unmatched_bank_total_count"] == \
               full["summary"]["unmatched_bank_total_count"], \
               "Page 2 bank total count diverged from full result"

        # GL counts also consistent
        assert page1["summary"]["unmatched_gl_total_count"] == \
               full["summary"]["unmatched_gl_total_count"], \
               "Page 1 GL total count diverged from full result"

        # Paginated items should sum to total when combined
        all_bank_ids = set()
        for txn in page1["unmatched_bank_transactions"]:
            all_bank_ids.add(txn["id"])
        for txn in page2["unmatched_bank_transactions"]:
            all_bank_ids.add(txn["id"])

        assert len(all_bank_ids) == full["summary"]["unmatched_bank_total_count"], \
            f"Paginated items ({len(all_bank_ids)}) don't sum to total ({full['summary']['unmatched_bank_total_count']})"

    def test_balance_equation_holds(self, seeded_reconciliation):
        """GL balance equation: opening + movement = closing."""
        db, reconciliation_id = seeded_reconciliation
        service = BankReconciliationService(db)

        result = service.get_outstanding_items(reconciliation_id)
        summary = result["summary"]

        # The balance equation must hold
        if all(k in summary for k in ["gl_opening_balance", "gl_movement", "gl_closing_balance"]):
            expected_closing = summary["gl_opening_balance"] + summary["gl_movement"]
            assert summary["gl_closing_balance"] == expected_closing, \
                f"Balance equation violated: {summary['gl_opening_balance']} + {summary['gl_movement']} != {summary['gl_closing_balance']}"

    def test_cancelled_gl_entries_never_in_outstanding(self, seeded_reconciliation):
        """Cancelled GL entries must never appear in outstanding items."""
        db, reconciliation_id = seeded_reconciliation
        service = BankReconciliationService(db)

        result = service.get_outstanding_items(reconciliation_id)

        # Verify no cancelled entries in results
        for entry in result["unmatched_gl_entries"]:
            # Check both dict and object access patterns
            is_cancelled = entry.get("is_cancelled") if isinstance(entry, dict) else getattr(entry, "is_cancelled", False)
            assert is_cancelled is not True, \
                f"Cancelled GL entry {entry.get('voucher_no', 'unknown')} found in outstanding items"

        # Also verify the specific cancelled entry from fixture is excluded
        voucher_nos = [
            e.get("voucher_no") if isinstance(e, dict) else getattr(e, "voucher_no", None)
            for e in result["unmatched_gl_entries"]
        ]
        assert "JE-CANCELLED" not in voucher_nos, \
            "JE-CANCELLED should be excluded from outstanding items"

    def test_reconciled_transactions_excluded_from_outstanding(
        self, seeded_reconciliation
    ):
        """Reconciled bank transactions must not appear in outstanding items."""
        db, reconciliation_id = seeded_reconciliation
        service = BankReconciliationService(db)

        result = service.get_outstanding_items(reconciliation_id)

        # The seeded fixture has 4 bank transactions: 3 unreconciled, 1 reconciled
        # Only the 3 unreconciled should appear
        assert result["summary"]["unmatched_bank_total_count"] == 3, \
            "Expected exactly 3 unreconciled bank transactions"

        # Verify no reconciled status in results
        for txn in result["unmatched_bank_transactions"]:
            status = txn.get("status") if isinstance(txn, dict) else getattr(txn, "status", None)
            if status is not None:
                assert status != BankTransactionStatus.RECONCILED, \
                    "Reconciled transaction found in outstanding items"
                assert str(status) != "RECONCILED", \
                    "Reconciled transaction (string) found in outstanding items"

    def test_amounts_sum_correctly(self, seeded_reconciliation):
        """Total amounts in summary must equal sum of individual items."""
        db, reconciliation_id = seeded_reconciliation
        service = BankReconciliationService(db)

        # Get full result to check all items
        result = service.get_outstanding_items(reconciliation_id)

        # Sum bank transaction amounts
        bank_total = Decimal("0")
        for txn in result["unmatched_bank_transactions"]:
            deposit = txn.get("deposit", Decimal("0")) if isinstance(txn, dict) else getattr(txn, "deposit", Decimal("0"))
            withdrawal = txn.get("withdrawal", Decimal("0")) if isinstance(txn, dict) else getattr(txn, "withdrawal", Decimal("0"))
            bank_total += (deposit or Decimal("0")) - (withdrawal or Decimal("0"))

        # Sum GL entry amounts
        gl_total = Decimal("0")
        for entry in result["unmatched_gl_entries"]:
            debit = entry.get("debit", Decimal("0")) if isinstance(entry, dict) else getattr(entry, "debit", Decimal("0"))
            credit = entry.get("credit", Decimal("0")) if isinstance(entry, dict) else getattr(entry, "credit", Decimal("0"))
            gl_total += (debit or Decimal("0")) - (credit or Decimal("0"))

        # Verify totals in summary match calculated sums
        summary = result["summary"]
        if "unmatched_bank_total_amount" in summary:
            assert summary["unmatched_bank_total_amount"] == bank_total, \
                f"Bank amount mismatch: summary={summary['unmatched_bank_total_amount']}, calculated={bank_total}"
        if "unmatched_gl_total_amount" in summary:
            assert summary["unmatched_gl_total_amount"] == gl_total, \
                f"GL amount mismatch: summary={summary['unmatched_gl_total_amount']}, calculated={gl_total}"
