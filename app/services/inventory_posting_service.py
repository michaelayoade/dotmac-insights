"""Service for posting inventory transactions to the General Ledger."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.inventory import StockEntry, StockLedgerEntry
    from app.models.accounting import JournalEntry


class InventoryPostingService:
    """
    Creates GL entries for inventory movements.

    Standard accounting entries:
    - Material Receipt: DR Inventory Asset, CR GRNI/AP
    - Material Issue: DR COGS/Expense, CR Inventory Asset
    - Material Transfer: DR Target Inventory, CR Source Inventory
    """

    # Default GL accounts (should be configurable via settings)
    DEFAULT_INVENTORY_ACCOUNT = "1310 - Inventory - Stock"
    DEFAULT_COGS_ACCOUNT = "5100 - Cost of Goods Sold"
    DEFAULT_GRNI_ACCOUNT = "2110 - Goods Received Not Invoiced"
    DEFAULT_STOCK_ADJUSTMENT_ACCOUNT = "5900 - Stock Adjustment"

    def __init__(self, db: Session):
        self.db = db

    def post_stock_entry(
        self,
        stock_entry: "StockEntry",
        inventory_account: Optional[str] = None,
        expense_account: Optional[str] = None,
        contra_account: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Optional["JournalEntry"]:
        """
        Post a stock entry to the GL based on its type.

        Args:
            stock_entry: The stock entry to post
            inventory_account: Override default inventory account
            expense_account: Override default expense/COGS account
            contra_account: Override default contra account (GRNI for receipts, etc.)
            user_id: ID of user performing the action

        Returns:
            JournalEntry if created, None if entry type doesn't require GL posting
        """
        entry_type = stock_entry.stock_entry_type or ""

        if "Receipt" in entry_type:
            return self._post_material_receipt(
                stock_entry, inventory_account, contra_account, user_id
            )
        elif "Issue" in entry_type:
            return self._post_material_issue(
                stock_entry, inventory_account, expense_account, user_id
            )
        elif "Transfer" in entry_type:
            return self._post_material_transfer(stock_entry, user_id)
        elif entry_type == "Manufacture":
            return self._post_manufacture(stock_entry, user_id)
        elif entry_type == "Repack":
            return self._post_repack(stock_entry, user_id)
        else:
            # Unknown type - create stock adjustment entry
            return self._post_stock_adjustment(stock_entry, user_id)

    def _post_material_receipt(
        self,
        stock_entry: "StockEntry",
        inventory_account: Optional[str],
        contra_account: Optional[str],
        user_id: Optional[int],
    ) -> "JournalEntry":
        """
        Post material receipt to GL.
        DR: Inventory Asset (increase stock value)
        CR: GRNI/AP (liability for goods received)
        """
        from app.models.accounting import JournalEntry, JournalEntryType

        inv_account = inventory_account or self.DEFAULT_INVENTORY_ACCOUNT
        grni_account = contra_account or self.DEFAULT_GRNI_ACCOUNT
        amount = stock_entry.total_incoming_value or Decimal("0")

        journal_entry = JournalEntry(
            voucher_type=JournalEntryType.JOURNAL_ENTRY,
            posting_date=stock_entry.posting_date or datetime.utcnow(),
            company=stock_entry.company,
            total_debit=amount,
            total_credit=amount,
            user_remark=f"Stock Receipt: {stock_entry.erpnext_id or stock_entry.id}",
            docstatus=1,  # Submitted
        )
        self.db.add(journal_entry)
        self.db.flush()

        # Create journal entry items
        self._create_journal_entry_item(
            journal_entry.id,
            inv_account,
            debit=amount,
            credit=Decimal("0"),
            reference_type="Stock Entry",
            reference_name=str(stock_entry.id),
        )
        self._create_journal_entry_item(
            journal_entry.id,
            grni_account,
            debit=Decimal("0"),
            credit=amount,
            reference_type="Stock Entry",
            reference_name=str(stock_entry.id),
        )

        return journal_entry

    def _post_material_issue(
        self,
        stock_entry: "StockEntry",
        inventory_account: Optional[str],
        expense_account: Optional[str],
        user_id: Optional[int],
    ) -> "JournalEntry":
        """
        Post material issue to GL.
        DR: COGS/Expense (cost of goods sold or consumed)
        CR: Inventory Asset (decrease stock value)
        """
        from app.models.accounting import JournalEntry, JournalEntryType

        inv_account = inventory_account or self.DEFAULT_INVENTORY_ACCOUNT
        cogs_account = expense_account or self.DEFAULT_COGS_ACCOUNT
        amount = stock_entry.total_outgoing_value or Decimal("0")

        journal_entry = JournalEntry(
            voucher_type=JournalEntryType.JOURNAL_ENTRY,
            posting_date=stock_entry.posting_date or datetime.utcnow(),
            company=stock_entry.company,
            total_debit=amount,
            total_credit=amount,
            user_remark=f"Stock Issue: {stock_entry.erpnext_id or stock_entry.id}",
            docstatus=1,
        )
        self.db.add(journal_entry)
        self.db.flush()

        self._create_journal_entry_item(
            journal_entry.id,
            cogs_account,
            debit=amount,
            credit=Decimal("0"),
            reference_type="Stock Entry",
            reference_name=str(stock_entry.id),
        )
        self._create_journal_entry_item(
            journal_entry.id,
            inv_account,
            debit=Decimal("0"),
            credit=amount,
            reference_type="Stock Entry",
            reference_name=str(stock_entry.id),
        )

        return journal_entry

    def _post_material_transfer(
        self,
        stock_entry: "StockEntry",
        user_id: Optional[int],
    ) -> "JournalEntry":
        """
        Post material transfer to GL.
        If warehouses have different stock accounts:
        DR: Target Warehouse Inventory Account
        CR: Source Warehouse Inventory Account

        If same account, no GL entry needed (internal transfer).
        """
        from app.models.accounting import JournalEntry, JournalEntryType

        # For simplicity, assume all warehouses use same inventory account
        # In a full implementation, would look up warehouse-specific accounts
        source_account = self.DEFAULT_INVENTORY_ACCOUNT
        target_account = self.DEFAULT_INVENTORY_ACCOUNT

        # If same account, no GL entry needed
        if source_account == target_account:
            return None

        amount = stock_entry.total_amount or Decimal("0")

        journal_entry = JournalEntry(
            voucher_type=JournalEntryType.JOURNAL_ENTRY,
            posting_date=stock_entry.posting_date or datetime.utcnow(),
            company=stock_entry.company,
            total_debit=amount,
            total_credit=amount,
            user_remark=f"Stock Transfer: {stock_entry.from_warehouse} → {stock_entry.to_warehouse}",
            docstatus=1,
        )
        self.db.add(journal_entry)
        self.db.flush()

        self._create_journal_entry_item(
            journal_entry.id,
            target_account,
            debit=amount,
            credit=Decimal("0"),
            reference_type="Stock Entry",
            reference_name=str(stock_entry.id),
        )
        self._create_journal_entry_item(
            journal_entry.id,
            source_account,
            debit=Decimal("0"),
            credit=amount,
            reference_type="Stock Entry",
            reference_name=str(stock_entry.id),
        )

        return journal_entry

    def _post_manufacture(
        self,
        stock_entry: "StockEntry",
        user_id: Optional[int],
    ) -> Optional["JournalEntry"]:
        """
        Post manufacture entry to GL.
        Converts raw materials to finished goods - typically no GL impact
        if same inventory account is used.
        """
        # Manufacturing typically doesn't create GL entries unless
        # there's a valuation difference
        if stock_entry.value_difference and stock_entry.value_difference != Decimal("0"):
            return self._post_stock_adjustment(stock_entry, user_id)
        return None

    def _post_repack(
        self,
        stock_entry: "StockEntry",
        user_id: Optional[int],
    ) -> Optional["JournalEntry"]:
        """
        Post repack entry to GL.
        Similar to manufacture - only creates entry if there's a value difference.
        """
        if stock_entry.value_difference and stock_entry.value_difference != Decimal("0"):
            return self._post_stock_adjustment(stock_entry, user_id)
        return None

    def _post_stock_adjustment(
        self,
        stock_entry: "StockEntry",
        user_id: Optional[int],
    ) -> "JournalEntry":
        """
        Post stock adjustment to GL for value differences.
        DR/CR: Inventory Asset
        CR/DR: Stock Adjustment Expense
        """
        from app.models.accounting import JournalEntry, JournalEntryType

        amount = abs(stock_entry.value_difference or stock_entry.total_amount or Decimal("0"))
        is_positive = (stock_entry.value_difference or stock_entry.total_amount or Decimal("0")) > 0

        journal_entry = JournalEntry(
            voucher_type=JournalEntryType.JOURNAL_ENTRY,
            posting_date=stock_entry.posting_date or datetime.utcnow(),
            company=stock_entry.company,
            total_debit=amount,
            total_credit=amount,
            user_remark=f"Stock Adjustment: {stock_entry.erpnext_id or stock_entry.id}",
            docstatus=1,
        )
        self.db.add(journal_entry)
        self.db.flush()

        if is_positive:
            # Increase in value: DR Inventory, CR Adjustment
            self._create_journal_entry_item(
                journal_entry.id,
                self.DEFAULT_INVENTORY_ACCOUNT,
                debit=amount,
                credit=Decimal("0"),
                reference_type="Stock Entry",
                reference_name=str(stock_entry.id),
            )
            self._create_journal_entry_item(
                journal_entry.id,
                self.DEFAULT_STOCK_ADJUSTMENT_ACCOUNT,
                debit=Decimal("0"),
                credit=amount,
                reference_type="Stock Entry",
                reference_name=str(stock_entry.id),
            )
        else:
            # Decrease in value: DR Adjustment, CR Inventory
            self._create_journal_entry_item(
                journal_entry.id,
                self.DEFAULT_STOCK_ADJUSTMENT_ACCOUNT,
                debit=amount,
                credit=Decimal("0"),
                reference_type="Stock Entry",
                reference_name=str(stock_entry.id),
            )
            self._create_journal_entry_item(
                journal_entry.id,
                self.DEFAULT_INVENTORY_ACCOUNT,
                debit=Decimal("0"),
                credit=amount,
                reference_type="Stock Entry",
                reference_name=str(stock_entry.id),
            )

        return journal_entry

    def _create_journal_entry_item(
        self,
        journal_entry_id: int,
        account: str,
        debit: Decimal,
        credit: Decimal,
        reference_type: Optional[str] = None,
        reference_name: Optional[str] = None,
    ) -> None:
        """Helper to create a journal entry line item."""
        # Note: This assumes a JournalEntryItem model exists
        # If not, we'd need to create it or use a different approach
        from sqlalchemy import text

        self.db.execute(
            text("""
                INSERT INTO journal_entry_items
                (journal_entry_id, account, debit, credit, reference_type, reference_name, created_at)
                VALUES (:je_id, :account, :debit, :credit, :ref_type, :ref_name, :created_at)
            """),
            {
                "je_id": journal_entry_id,
                "account": account,
                "debit": debit,
                "credit": credit,
                "ref_type": reference_type,
                "ref_name": reference_name,
                "created_at": datetime.utcnow(),
            }
        )

    def reverse_posting(
        self,
        journal_entry: "JournalEntry",
        reason: str,
        user_id: Optional[int] = None,
    ) -> "JournalEntry":
        """
        Create a reversal entry for a previously posted journal entry.
        Swaps debits and credits.
        """
        from app.models.accounting import JournalEntry, JournalEntryType

        reversal = JournalEntry(
            voucher_type=JournalEntryType.JOURNAL_ENTRY,
            posting_date=datetime.utcnow(),
            company=journal_entry.company,
            total_debit=journal_entry.total_credit,
            total_credit=journal_entry.total_debit,
            user_remark=f"Reversal of {journal_entry.id}: {reason}",
            docstatus=1,
        )
        self.db.add(reversal)
        self.db.flush()

        # Copy and reverse line items
        from sqlalchemy import text
        result = self.db.execute(
            text("SELECT account, debit, credit, reference_type, reference_name FROM journal_entry_items WHERE journal_entry_id = :je_id"),
            {"je_id": journal_entry.id}
        )
        for row in result:
            self._create_journal_entry_item(
                reversal.id,
                row.account,
                debit=row.credit,  # Swap
                credit=row.debit,  # Swap
                reference_type=row.reference_type,
                reference_name=row.reference_name,
            )

        return reversal


class StockReceiptPostingService(InventoryPostingService):
    """Specialized service for posting stock receipts from purchase bills."""

    def post_from_purchase_invoice(
        self,
        purchase_invoice_id: int,
        items: List[dict],
        warehouse: str,
        user_id: Optional[int] = None,
    ) -> tuple["StockEntry", Optional["JournalEntry"]]:
        """
        Create a stock receipt from a purchase invoice and post to GL.

        Args:
            purchase_invoice_id: ID of the source purchase invoice
            items: List of items to receive [{item_code, qty, rate, amount}]
            warehouse: Target warehouse
            user_id: User performing the action

        Returns:
            Tuple of (StockEntry, JournalEntry or None)
        """
        from app.models.inventory import StockEntry, StockEntryDetail

        total_value = sum(Decimal(str(item.get("amount", 0))) for item in items)

        stock_entry = StockEntry(
            stock_entry_type="Material Receipt",
            posting_date=datetime.utcnow(),
            to_warehouse=warehouse,
            total_incoming_value=total_value,
            total_amount=total_value,
            purchase_receipt=f"PI-{purchase_invoice_id}",
            docstatus=1,
            origin_system="local",
            created_by_id=user_id,
        )
        self.db.add(stock_entry)
        self.db.flush()

        for idx, item in enumerate(items):
            detail = StockEntryDetail(
                stock_entry_id=stock_entry.id,
                item_code=item.get("item_code"),
                item_name=item.get("item_name"),
                qty=Decimal(str(item.get("qty", 0))),
                t_warehouse=warehouse,
                basic_rate=Decimal(str(item.get("rate", 0))),
                basic_amount=Decimal(str(item.get("amount", 0))),
                valuation_rate=Decimal(str(item.get("rate", 0))),
                amount=Decimal(str(item.get("amount", 0))),
                idx=idx,
            )
            self.db.add(detail)

        # Post to GL
        journal_entry = self.post_stock_entry(stock_entry, user_id=user_id)

        return stock_entry, journal_entry


class StockIssuePostingService(InventoryPostingService):
    """Specialized service for posting stock issues for sales invoices."""

    def post_from_sales_invoice(
        self,
        invoice_id: int,
        items: List[dict],
        warehouse: str,
        user_id: Optional[int] = None,
    ) -> tuple["StockEntry", Optional["JournalEntry"]]:
        """
        Create a stock issue from a sales invoice and post COGS to GL.

        Args:
            invoice_id: ID of the source sales invoice
            items: List of items to issue [{item_code, qty, valuation_rate, amount}]
            warehouse: Source warehouse
            user_id: User performing the action

        Returns:
            Tuple of (StockEntry, JournalEntry or None)
        """
        from app.models.inventory import StockEntry, StockEntryDetail

        total_value = sum(Decimal(str(item.get("amount", 0))) for item in items)

        stock_entry = StockEntry(
            stock_entry_type="Material Issue",
            posting_date=datetime.utcnow(),
            from_warehouse=warehouse,
            total_outgoing_value=total_value,
            total_amount=total_value,
            delivery_note=f"INV-{invoice_id}",
            docstatus=1,
            origin_system="local",
            created_by_id=user_id,
        )
        self.db.add(stock_entry)
        self.db.flush()

        for idx, item in enumerate(items):
            detail = StockEntryDetail(
                stock_entry_id=stock_entry.id,
                item_code=item.get("item_code"),
                item_name=item.get("item_name"),
                qty=Decimal(str(item.get("qty", 0))),
                s_warehouse=warehouse,
                basic_rate=Decimal(str(item.get("valuation_rate", 0))),
                basic_amount=Decimal(str(item.get("amount", 0))),
                valuation_rate=Decimal(str(item.get("valuation_rate", 0))),
                amount=Decimal(str(item.get("amount", 0))),
                idx=idx,
            )
            self.db.add(detail)

        # Post to GL (COGS)
        journal_entry = self.post_stock_entry(stock_entry, user_id=user_id)

        return stock_entry, journal_entry
