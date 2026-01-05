"""Dashboard service - business logic for accounting dashboard.

This service encapsulates dashboard-related business logic:
- Core dashboard metrics (balance sheet summary, P&L, AR/AP, bank balances)
- Dashboard bundle (aggregates multiple reports)

Uses AccountingSettingsService for configurable limits and caching.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.accounting.helpers import ASSET_ACCOUNT_TYPES, LIABILITY_ACCOUNT_TYPES
from app.models.accounting import (
    Account,
    AccountType,
    BankTransaction,
    GLEntry,
    PurchaseInvoice,
    PurchaseInvoiceStatus,
)
from app.models.invoice import Invoice, InvoiceStatus

from .dashboard_types import (
    ActivityCounts,
    BalanceSummary,
    BankBalance,
    DashboardBundle,
    DashboardBundleFilters,
    DashboardData,
    DashboardFilters,
    DatePeriod,
    PerformanceSummary,
    ReceivablesPayablesSummary,
)
from .settings import AccountingSettingsService

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["DashboardService"]


def _get_effective_root_type(acc: Account) -> Optional[AccountType]:
    """Determine effective root type for an account.

    Handles special account types that may override root_type classification.

    Args:
        acc: Account model instance

    Returns:
        Effective AccountType or None
    """
    if not acc:
        return None

    # Check if account_type overrides root_type
    if acc.account_type in ASSET_ACCOUNT_TYPES:
        return AccountType.ASSET
    if acc.account_type in LIABILITY_ACCOUNT_TYPES:
        return AccountType.LIABILITY

    return acc.root_type


class DashboardService:
    """Service for accounting dashboard business logic.

    Args:
        db: SQLAlchemy database session.
        settings_service: Accounting settings service for configuration.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(
        self,
        db: Session,
        settings_service: AccountingSettingsService,
        principal: Optional["Principal"] = None,
    ) -> None:
        self.db = db
        self.settings = settings_service
        self.principal = principal

    # -------------------------------------------------------------------------
    # Core Dashboard
    # -------------------------------------------------------------------------

    def get_dashboard(
        self,
        filters: Optional[DashboardFilters] = None,
        company: Optional[str] = None,
    ) -> DashboardData:
        """Get accounting dashboard overview.

        Shows key financial metrics including:
        - Balance sheet summary (assets, liabilities, equity)
        - Performance metrics (income, expenses, profit)
        - AR/AP summary
        - Bank balances
        - Activity counts

        Args:
            filters: Date range filters (defaults to YTD).
            company: Company code for settings lookup.

        Returns:
            DashboardData with all key metrics.
        """
        if filters is None:
            filters = DashboardFilters()

        end_dt = filters.end_date or date.today()
        start_dt = filters.start_date or date(end_dt.year, 1, 1)

        # Get account balances (cumulative to end_dt)
        balances = self.db.query(
            GLEntry.account,
            func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= end_dt,
        ).group_by(GLEntry.account).all()

        balance_map = {r.account: Decimal(str(r.balance or 0)) for r in balances}

        # Get accounts with their types - filter to only active leaf accounts
        accounts = {
            acc.erpnext_id: acc
            for acc in self.db.query(Account).filter(
                Account.disabled == False,
                Account.is_group == False,  # Only leaf accounts have balances
            ).all()
        }

        # Calculate totals by effective root type
        total_assets = sum(
            balance_map.get(acc_id, Decimal("0"))
            for acc_id, acc in accounts.items()
            if _get_effective_root_type(acc) == AccountType.ASSET
        )
        total_liabilities = sum(
            -balance_map.get(acc_id, Decimal("0"))
            for acc_id, acc in accounts.items()
            if _get_effective_root_type(acc) == AccountType.LIABILITY
        )
        total_equity = sum(
            -balance_map.get(acc_id, Decimal("0"))
            for acc_id, acc in accounts.items()
            if _get_effective_root_type(acc) == AccountType.EQUITY
        )

        # Period income/expenses (within date range)
        period_entries = self.db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("debit"),
            func.sum(GLEntry.credit).label("credit"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= start_dt,
            GLEntry.posting_date <= end_dt,
        ).group_by(GLEntry.account).all()

        period_map: Dict[str, Dict[str, Decimal]] = {
            r.account: {
                "debit": Decimal(str(r.debit or 0)),
                "credit": Decimal(str(r.credit or 0)),
            }
            for r in period_entries
        }

        total_income = sum(
            period_map.get(acc_id, {}).get("credit", Decimal("0")) -
            period_map.get(acc_id, {}).get("debit", Decimal("0"))
            for acc_id, acc in accounts.items()
            if _get_effective_root_type(acc) == AccountType.INCOME
        )
        total_expenses = sum(
            period_map.get(acc_id, {}).get("debit", Decimal("0")) -
            period_map.get(acc_id, {}).get("credit", Decimal("0"))
            for acc_id, acc in accounts.items()
            if _get_effective_root_type(acc) == AccountType.EXPENSE
        )

        # AR/AP summaries
        total_receivable = self.db.query(func.sum(Invoice.balance)).filter(
            Invoice.balance > 0,
            Invoice.status.notin_([InvoiceStatus.CANCELLED, InvoiceStatus.REFUNDED]),
        ).scalar() or Decimal("0")

        total_payable = self.db.query(func.sum(PurchaseInvoice.outstanding_amount)).filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.status.notin_([PurchaseInvoiceStatus.CANCELLED]),
        ).scalar() or Decimal("0")

        # Bank balances
        bank_balances: List[BankBalance] = []
        for acc_id, acc in accounts.items():
            if acc.account_type == "Bank":
                balance = balance_map.get(acc_id, Decimal("0"))
                if balance != 0:
                    bank_balances.append(BankBalance(
                        account=acc.account_name or acc_id,
                        balance=balance,
                    ))

        # Sort bank balances by balance descending
        bank_balances.sort(key=lambda x: x.balance, reverse=True)

        # Recent transactions count
        recent_gl_count = self.db.query(func.count(GLEntry.id)).filter(
            GLEntry.posting_date >= start_dt,
            GLEntry.posting_date <= end_dt,
            GLEntry.is_cancelled == False,
        ).scalar() or 0

        recent_bank_txn_count = self.db.query(func.count(BankTransaction.id)).filter(
            BankTransaction.date >= start_dt,
            BankTransaction.date <= end_dt,
        ).scalar() or 0

        # Calculate net profit and margin
        net_profit = total_income - total_expenses
        if total_income and total_income > 0:
            profit_margin = Decimal(str(round((net_profit / total_income) * 100, 2)))
        else:
            profit_margin = Decimal("0")

        return DashboardData(
            period=DatePeriod(start_date=start_dt, end_date=end_dt),
            summary=BalanceSummary(
                total_assets=total_assets,
                total_liabilities=total_liabilities,
                total_equity=total_equity,
                net_worth=total_assets - total_liabilities,
            ),
            performance=PerformanceSummary(
                total_income=total_income,
                total_expenses=total_expenses,
                net_profit=net_profit,
                profit_margin=Decimal(str(profit_margin)),
            ),
            receivables_payables=ReceivablesPayablesSummary(
                total_receivable=Decimal(str(total_receivable)),
                total_payable=Decimal(str(total_payable)),
                net_position=Decimal(str(total_receivable)) - Decimal(str(total_payable)),
            ),
            bank_balances=bank_balances,
            activity=ActivityCounts(
                gl_entries_count=int(recent_gl_count),
                bank_transactions_count=int(recent_bank_txn_count),
            ),
        )

    # -------------------------------------------------------------------------
    # Dashboard Bundle
    # -------------------------------------------------------------------------

    def get_dashboard_bundle(
        self,
        filters: Optional[DashboardBundleFilters] = None,
        company: Optional[str] = None,
    ) -> DashboardBundle:
        """Get bundled accounting dashboard payload.

        Returns dashboard, balance sheet, income statement, cash flow,
        bank accounts, and receivables/payables summaries in one call.

        This method orchestrates other services to build the complete bundle.
        It returns dict representations for API compatibility.

        Args:
            filters: Bundle filters (currency, dates, top_n).
            company: Company code for settings lookup.

        Returns:
            DashboardBundle with all reports.

        Note:
            This service method returns dicts from other services/routes.
            For full service-layer integration, those would also be services.
        """
        if filters is None:
            filters = DashboardBundleFilters()

        # Get configurable limits
        query_limits = self.settings.get_query_limits(company)
        top_n = min(filters.top_n, query_limits.max_top_items)

        # Effective as_of date for point-in-time reports
        effective_as_of = filters.as_of_date or filters.end_date

        # Build dashboard filters
        dashboard_filters = DashboardFilters(
            start_date=filters.start_date,
            end_date=filters.end_date,
        )

        # Get core dashboard
        dashboard = self.get_dashboard(dashboard_filters, company)

        # For the bundle, we need to call other routes/services
        # This is a placeholder - in full implementation, these would be service calls
        # For now, return the dashboard and empty placeholders for other reports
        # The route handler can still call the existing route functions

        return DashboardBundle(
            currency=filters.currency,
            dashboard=dashboard.to_dict(),
            balance_sheet={},  # To be filled by route or ReportsService
            income_statement={},  # To be filled by route or ReportsService
            cash_flow={},  # To be filled by route or ReportsService
            receivables_outstanding={},  # To be filled by ReceivablesService
            payables_outstanding={},  # To be filled by PayablesService
            bank_accounts={},  # To be filled by BankingService
        )

    def build_full_bundle(
        self,
        filters: Optional[DashboardBundleFilters] = None,
        balance_sheet: Optional[Dict[str, Any]] = None,
        income_statement: Optional[Dict[str, Any]] = None,
        cash_flow: Optional[Dict[str, Any]] = None,
        receivables_outstanding: Optional[Dict[str, Any]] = None,
        payables_outstanding: Optional[Dict[str, Any]] = None,
        bank_accounts: Optional[Dict[str, Any]] = None,
        company: Optional[str] = None,
    ) -> DashboardBundle:
        """Build full dashboard bundle with provided report data.

        This is a helper method for routes that need to assemble the bundle
        from multiple service calls.

        Args:
            filters: Bundle filters.
            balance_sheet: Balance sheet report data.
            income_statement: Income statement report data.
            cash_flow: Cash flow report data.
            receivables_outstanding: AR outstanding data.
            payables_outstanding: AP outstanding data.
            bank_accounts: Bank accounts data.
            company: Company code.

        Returns:
            DashboardBundle with all provided reports.
        """
        if filters is None:
            filters = DashboardBundleFilters()

        # Build dashboard filters
        dashboard_filters = DashboardFilters(
            start_date=filters.start_date,
            end_date=filters.end_date,
        )

        # Get core dashboard
        dashboard = self.get_dashboard(dashboard_filters, company)

        return DashboardBundle(
            currency=filters.currency,
            dashboard=dashboard.to_dict(),
            balance_sheet=balance_sheet or {},
            income_statement=income_statement or {},
            cash_flow=cash_flow or {},
            receivables_outstanding=receivables_outstanding or {},
            payables_outstanding=payables_outstanding or {},
            bank_accounts=bank_accounts or {},
        )
