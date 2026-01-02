"""Ledger service - business logic for Chart of Accounts and GL entries.

This service encapsulates all ledger-related business logic:
- Chart of Accounts CRUD
- Account balance calculations
- Account ledger with running balance
- GL Entry CRUD and queries

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.accounting import Account, AccountType, GLEntry
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .ledger_types import (
    AccountBalanceInfo,
    AccountCreateData,
    AccountFilters,
    AccountLedgerFilters,
    AccountLedgerResult,
    AccountUpdateData,
    ChartOfAccountsNode,
    GLEntryCreateData,
    GLEntryFilters,
    GLEntryUpdateData,
    LedgerEntry,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["LedgerService"]

# Allowed sort columns for GL entries
ALLOWED_GL_SORTS = {
    "posting_date",
    "account",
    "party",
    "debit",
    "credit",
    "voucher_type",
    "voucher_no",
    "cost_center",
    "id",
}


class LedgerService:
    """Service for Chart of Accounts and GL Entry business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Account Queries
    # -------------------------------------------------------------------------

    def list_accounts(
        self,
        filters: Optional[AccountFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Account]:
        """List accounts with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing accounts and total count.

        Raises:
            ValidationError: If search query is too short.
        """
        if filters is None:
            filters = AccountFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(Account)
        query = scoped_query(query, self.principal)

        if filters.root_type:
            query = query.filter(Account.root_type == filters.root_type)

        if filters.account_type:
            query = query.filter(Account.account_type == filters.account_type)

        if filters.is_group is not None:
            query = query.filter(Account.is_group == filters.is_group)

        if not filters.include_disabled:
            query = query.filter(Account.disabled == False)

        if filters.search:
            if len(filters.search) < 2:
                raise ValidationError(
                    "Search query must be at least 2 characters"
                )
            query = query.filter(Account.account_name.ilike(f"%{filters.search}%"))

        query = query.order_by(Account.account_name)
        return paginate(query, pagination)

    def get_account(self, account_id: int) -> Account:
        """Get an account by ID.

        Args:
            account_id: The account ID.

        Returns:
            The Account object.

        Raises:
            NotFoundError: If account not found.
        """
        account = (
            self.db.query(Account).filter(Account.id == account_id).first()
        )
        if not account:
            raise NotFoundError(f"Account {account_id} not found")
        return account

    def get_account_balance(self, account: Account) -> AccountBalanceInfo:
        """Calculate current balance for an account.

        Args:
            account: The Account object.

        Returns:
            AccountBalanceInfo with balance details.
        """
        balance_result = (
            self.db.query(
                func.sum(GLEntry.debit).label("total_debit"),
                func.sum(GLEntry.credit).label("total_credit"),
            )
            .filter(
                GLEntry.account == account.erpnext_id,
                GLEntry.is_cancelled == False,
            )
            .first()
        )

        totals = balance_result._mapping if balance_result else {}
        total_debit = totals.get("total_debit") or Decimal("0")
        total_credit = totals.get("total_credit") or Decimal("0")
        balance = total_debit - total_credit

        # Determine normal balance type
        if account.root_type in [AccountType.ASSET, AccountType.EXPENSE]:
            normal_balance = "debit"
        else:
            normal_balance = "credit"

        return AccountBalanceInfo(
            total_debit=total_debit,
            total_credit=total_credit,
            balance=balance,
            balance_type="Dr" if balance >= 0 else "Cr",
            normal_balance=normal_balance,
        )

    def get_account_ledger(
        self,
        account_id: int,
        filters: Optional[AccountLedgerFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> AccountLedgerResult:
        """Get ledger entries for an account with running balance.

        Args:
            account_id: The account ID.
            filters: Optional filter criteria.
            pagination: Pagination parameters.

        Returns:
            AccountLedgerResult with entries and running balance.

        Raises:
            NotFoundError: If account not found.
        """
        if filters is None:
            filters = AccountLedgerFilters()
        if pagination is None:
            pagination = PaginationParams()

        account = self.get_account(account_id)

        # Base query
        query = self.db.query(GLEntry).filter(
            GLEntry.account == account.erpnext_id,
            GLEntry.is_cancelled == False,
        )

        # Calculate opening balance (before start_date)
        opening_balance = Decimal("0")
        if filters.start_date:
            opening_result = (
                self.db.query(func.sum(GLEntry.debit - GLEntry.credit))
                .filter(
                    GLEntry.account == account.erpnext_id,
                    GLEntry.is_cancelled == False,
                    GLEntry.posting_date < filters.start_date,
                )
                .scalar()
            )
            opening_balance = opening_result or Decimal("0")
            query = query.filter(GLEntry.posting_date >= filters.start_date)

        if filters.end_date:
            query = query.filter(GLEntry.posting_date <= filters.end_date)

        if filters.party_type:
            query = query.filter(GLEntry.party_type == filters.party_type)

        if filters.party:
            query = query.filter(GLEntry.party.ilike(f"%{filters.party}%"))

        if filters.voucher_type:
            query = query.filter(GLEntry.voucher_type == filters.voucher_type)

        total = query.count()
        entries = (
            query.order_by(GLEntry.posting_date.asc(), GLEntry.id.asc())
            .offset(pagination.offset)
            .limit(pagination.limit)
            .all()
        )

        # Calculate running balance
        ledger_entries: List[LedgerEntry] = []
        running_balance = opening_balance
        for e in entries:
            running_balance += e.debit - e.credit
            ledger_entries.append(
                LedgerEntry(
                    id=e.id,
                    posting_date=e.posting_date.date() if e.posting_date else None,
                    party_type=e.party_type,
                    party=e.party,
                    debit=e.debit,
                    credit=e.credit,
                    balance=running_balance,
                    voucher_type=e.voucher_type,
                    voucher_no=e.voucher_no,
                    cost_center=e.cost_center,
                )
            )

        return AccountLedgerResult(
            account_id=account.id,
            account_name=account.account_name,
            root_type=account.root_type.value if account.root_type else None,
            start_date=filters.start_date,
            end_date=filters.end_date,
            opening_balance=opening_balance,
            closing_balance=running_balance if ledger_entries else opening_balance,
            total=total,
            entries=ledger_entries,
        )

    def get_chart_of_accounts(
        self,
        root_type: Optional[AccountType] = None,
        include_disabled: bool = False,
        include_balances: bool = True,
        as_of_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get chart of accounts as hierarchical tree with balances.

        Args:
            root_type: Filter by root type.
            include_disabled: Include disabled accounts.
            include_balances: Include account balances.
            as_of_date: Calculate balances as of this date.

        Returns:
            Dict with flat list, tree structure, and counts.
        """
        query = self.db.query(Account)

        if root_type:
            query = query.filter(Account.root_type == root_type)

        if not include_disabled:
            query = query.filter(Account.disabled == False)

        accounts = query.order_by(Account.account_name).all()

        # Calculate balances from GL entries if requested
        account_balances: Dict[str, float] = {}
        if include_balances:
            cutoff = as_of_date or date.today()
            balance_query = (
                self.db.query(
                    GLEntry.account,
                    func.sum(GLEntry.debit).label("total_debit"),
                    func.sum(GLEntry.credit).label("total_credit"),
                )
                .filter(
                    GLEntry.is_cancelled == False,
                    GLEntry.posting_date <= cutoff,
                )
                .group_by(GLEntry.account)
            )

            for row in balance_query.all():
                debit = row.total_debit or Decimal("0")
                credit = row.total_credit or Decimal("0")
                account_balances[row.account] = float(debit - credit)

        # Build tree structure
        def build_tree(
            accs: List[Account], parent: Optional[str] = None
        ) -> List[ChartOfAccountsNode]:
            tree = []
            for acc in accs:
                if acc.parent_account == parent:
                    balance = account_balances.get(acc.erpnext_id or "", 0.0)
                    node = ChartOfAccountsNode(
                        id=acc.id,
                        name=acc.account_name,
                        account_number=acc.account_number,
                        root_type=acc.root_type.value if acc.root_type else None,
                        account_type=acc.account_type,
                        is_group=acc.is_group,
                        disabled=acc.disabled,
                        balance=balance,
                        children=(
                            build_tree(accs, acc.erpnext_id) if acc.is_group else []
                        ),
                    )
                    tree.append(node)
            return tree

        # Build flat list
        flat_list = [
            {
                "id": acc.id,
                "erpnext_id": acc.erpnext_id,
                "name": acc.account_name,
                "account_number": acc.account_number,
                "parent_account": acc.parent_account,
                "root_type": acc.root_type.value if acc.root_type else None,
                "account_type": acc.account_type,
                "is_group": acc.is_group,
                "disabled": acc.disabled,
                "balance": account_balances.get(acc.erpnext_id or "", 0.0),
            }
            for acc in accounts
        ]

        # Group by root type
        by_root_type: Dict[str, int] = {}
        for acc in accounts:
            rt = acc.root_type.value if acc.root_type else "unknown"
            by_root_type[rt] = by_root_type.get(rt, 0) + 1

        return {
            "total": len(accounts),
            "by_root_type": by_root_type,
            "accounts": flat_list,
            "tree": build_tree(accounts, None),
        }

    def get_account_types_summary(self) -> Dict[str, Any]:
        """Get summary of accounts grouped by account type.

        Returns:
            Dict with account types and their counts.
        """
        type_counts = (
            self.db.query(
                Account.account_type,
                Account.root_type,
                func.count(Account.id).label("count"),
            )
            .filter(Account.disabled == False)
            .group_by(Account.account_type, Account.root_type)
            .all()
        )

        by_type: Dict[str, Dict] = {}
        for row in type_counts:
            acc_type = row.account_type or "Unspecified"
            if acc_type not in by_type:
                by_type[acc_type] = {"count": 0, "root_types": []}
            by_type[acc_type]["count"] += row.count
            rt = row.root_type.value if row.root_type else "unknown"
            if rt not in by_type[acc_type]["root_types"]:
                by_type[acc_type]["root_types"].append(rt)

        root_types = [rt.value for rt in AccountType]

        return {
            "root_types": root_types,
            "account_types": by_type,
            "total_types": len(by_type),
        }

    # -------------------------------------------------------------------------
    # Account CRUD
    # -------------------------------------------------------------------------

    def create_account(self, data: AccountCreateData) -> Account:
        """Create a new account.

        Args:
            data: Account creation data.

        Returns:
            The created Account (not yet committed).
        """
        account = Account(
            account_name=data.account_name,
            account_number=data.account_number,
            parent_account=data.parent_account,
            root_type=data.root_type,
            account_type=data.account_type,
            company=data.company,
            is_group=data.is_group,
            disabled=data.disabled,
            balance_must_be=data.balance_must_be,
        )
        self.db.add(account)
        self.db.flush()
        return account

    def update_account(
        self, account_id: int, data: AccountUpdateData
    ) -> Account:
        """Update an account.

        Args:
            account_id: The account ID.
            data: Fields to update.

        Returns:
            The updated Account (not yet committed).

        Raises:
            NotFoundError: If account not found.
        """
        account = self.get_account(account_id)

        if data.account_name is not None:
            account.account_name = data.account_name
        if data.account_number is not None:
            account.account_number = data.account_number
        if data.parent_account is not None:
            account.parent_account = data.parent_account
        if data.root_type is not None:
            account.root_type = data.root_type
        if data.account_type is not None:
            account.account_type = data.account_type
        if data.company is not None:
            account.company = data.company
        if data.is_group is not None:
            account.is_group = data.is_group
        if data.disabled is not None:
            account.disabled = data.disabled
        if data.balance_must_be is not None:
            account.balance_must_be = data.balance_must_be

        return account

    def disable_account(self, account_id: int) -> Account:
        """Disable an account (soft delete).

        Args:
            account_id: The account ID.

        Returns:
            The disabled Account (not yet committed).

        Raises:
            NotFoundError: If account not found.
        """
        account = self.get_account(account_id)
        account.disabled = True
        return account

    # -------------------------------------------------------------------------
    # GL Entry Queries
    # -------------------------------------------------------------------------

    def list_gl_entries(
        self,
        filters: Optional[GLEntryFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[GLEntry]:
        """List GL entries with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters.

        Returns:
            PaginatedResult containing GL entries and total count.

        Raises:
            ValidationError: If search query is too short.
        """
        if filters is None:
            filters = GLEntryFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(GLEntry)
        query = scoped_query(query, self.principal)

        if filters.account:
            query = query.filter(GLEntry.account.ilike(f"%{filters.account}%"))

        if filters.voucher_type:
            query = query.filter(GLEntry.voucher_type == filters.voucher_type)

        if filters.voucher_no:
            query = query.filter(GLEntry.voucher_no.ilike(f"%{filters.voucher_no}%"))

        if filters.party_type:
            query = query.filter(GLEntry.party_type == filters.party_type)

        if filters.party:
            query = query.filter(GLEntry.party.ilike(f"%{filters.party}%"))

        if filters.start_date:
            query = query.filter(GLEntry.posting_date >= filters.start_date)

        if filters.end_date:
            query = query.filter(GLEntry.posting_date <= filters.end_date)

        if filters.is_cancelled is not None:
            query = query.filter(GLEntry.is_cancelled == filters.is_cancelled)

        if filters.search:
            if len(filters.search) < 2:
                raise ValidationError(
                    "Search query must be at least 2 characters"
                )
            query = query.filter(
                or_(
                    GLEntry.account.ilike(f"%{filters.search}%"),
                    GLEntry.voucher_no.ilike(f"%{filters.search}%"),
                    GLEntry.party.ilike(f"%{filters.search}%"),
                )
            )

        # Sorting
        sort_key = (
            filters.sort_by if filters.sort_by in ALLOWED_GL_SORTS else "posting_date"
        )
        sort_column = getattr(GLEntry, sort_key, GLEntry.posting_date)
        if filters.sort_dir == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        return paginate(query, pagination)

    def get_gl_entry(self, entry_id: int) -> GLEntry:
        """Get a GL entry by ID.

        Args:
            entry_id: The GL entry ID.

        Returns:
            The GLEntry object.

        Raises:
            NotFoundError: If GL entry not found.
        """
        entry = self.db.query(GLEntry).filter(GLEntry.id == entry_id).first()
        if not entry:
            raise NotFoundError(f"GL entry {entry_id} not found")
        return entry

    # -------------------------------------------------------------------------
    # GL Entry CRUD
    # -------------------------------------------------------------------------

    def create_gl_entry(self, data: GLEntryCreateData) -> GLEntry:
        """Create a new GL entry.

        Args:
            data: GL entry creation data.

        Returns:
            The created GLEntry (not yet committed).
        """
        entry = GLEntry(
            posting_date=data.posting_date,
            account=data.account,
            party_type=data.party_type,
            party=data.party,
            debit=data.debit,
            credit=data.credit,
            debit_in_account_currency=(
                data.debit_in_account_currency
                if data.debit_in_account_currency is not None
                else data.debit
            ),
            credit_in_account_currency=(
                data.credit_in_account_currency
                if data.credit_in_account_currency is not None
                else data.credit
            ),
            voucher_type=data.voucher_type,
            voucher_no=data.voucher_no,
            cost_center=data.cost_center,
            company=data.company,
            fiscal_year=data.fiscal_year,
            is_cancelled=data.is_cancelled,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def update_gl_entry(self, entry_id: int, data: GLEntryUpdateData) -> GLEntry:
        """Update a GL entry.

        Args:
            entry_id: The GL entry ID.
            data: Fields to update.

        Returns:
            The updated GLEntry (not yet committed).

        Raises:
            NotFoundError: If GL entry not found.
        """
        entry = self.get_gl_entry(entry_id)

        if data.posting_date is not None:
            entry.posting_date = data.posting_date
        if data.account is not None:
            entry.account = data.account
        if data.party_type is not None:
            entry.party_type = data.party_type
        if data.party is not None:
            entry.party = data.party
        if data.debit is not None:
            entry.debit = data.debit
        if data.credit is not None:
            entry.credit = data.credit
        if data.debit_in_account_currency is not None:
            entry.debit_in_account_currency = data.debit_in_account_currency
        if data.credit_in_account_currency is not None:
            entry.credit_in_account_currency = data.credit_in_account_currency
        if data.voucher_type is not None:
            entry.voucher_type = data.voucher_type
        if data.voucher_no is not None:
            entry.voucher_no = data.voucher_no
        if data.cost_center is not None:
            entry.cost_center = data.cost_center
        if data.company is not None:
            entry.company = data.company
        if data.fiscal_year is not None:
            entry.fiscal_year = data.fiscal_year
        if data.is_cancelled is not None:
            entry.is_cancelled = data.is_cancelled

        return entry

    def delete_gl_entry(self, entry_id: int) -> None:
        """Delete a GL entry.

        Args:
            entry_id: The GL entry ID.

        Raises:
            NotFoundError: If GL entry not found.
        """
        entry = self.get_gl_entry(entry_id)
        self.db.delete(entry)
