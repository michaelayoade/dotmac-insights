"""Tests for IFRS reporting using internal account IDs."""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.accounting import AccountType
from app.services.accounting.reports import ReportsService


def _make_account(account_id: int, root_type: AccountType, account_type: str = ""):
    return SimpleNamespace(
        id=account_id,
        account_name=f"Account {account_id}",
        account_number=str(account_id),
        root_type=root_type,
        account_type=account_type,
        is_group=False,
    )


def test_trial_balance_view_uses_internal_account_ids():
    account_asset = _make_account(1, AccountType.ASSET, "Receivable")
    account_liability = _make_account(2, AccountType.LIABILITY, "Payable")
    accounts = [account_asset, account_liability]

    db = MagicMock()
    account_query = MagicMock()
    account_query.filter.return_value = account_query
    account_query.order_by.return_value = account_query
    account_query.all.return_value = accounts
    db.query.return_value = account_query

    service = ReportsService(db)
    service._get_gl_sums = MagicMock(return_value={
        1: {"debit": Decimal("100.00"), "credit": Decimal("25.00")},
        2: {"debit": Decimal("10.00"), "credit": Decimal("60.00")},
    })

    result = service.get_trial_balance_view(as_of_date=datetime.utcnow())
    rows = result["accounts"]

    assert len(rows) == 2
    # Asset should show debit balance
    assert rows[0]["debit"] == Decimal("75.00")
    assert rows[0]["credit"] == Decimal("0")
    # Liability should show credit balance
    assert rows[1]["debit"] == Decimal("0")
    assert rows[1]["credit"] == Decimal("50.00")


def test_balance_sheet_uses_internal_account_ids():
    asset = _make_account(10, AccountType.ASSET, "Cash")
    liability = _make_account(20, AccountType.LIABILITY, "Payable")
    equity = _make_account(30, AccountType.EQUITY, "Equity")
    income = _make_account(40, AccountType.INCOME, "Income")
    expense = _make_account(50, AccountType.EXPENSE, "Expense")
    accounts = [asset, liability, equity, income, expense]

    db = MagicMock()
    account_query = MagicMock()
    account_query.filter.return_value = account_query
    account_query.order_by.return_value = account_query
    account_query.all.return_value = accounts

    gl_query = MagicMock()
    gl_query.filter.return_value = gl_query
    gl_query.scalar.return_value = Decimal("0")

    def _query_side_effect(model, *args, **kwargs):
        if getattr(model, "__name__", None) == "Account":
            return account_query
        return gl_query

    db.query.side_effect = _query_side_effect

    service = ReportsService(db)
    service._get_gl_sums = MagicMock(return_value={
        10: {"debit": Decimal("500"), "credit": Decimal("0")},
        20: {"debit": Decimal("0"), "credit": Decimal("200")},
        30: {"debit": Decimal("0"), "credit": Decimal("100")},
    })

    result = service.get_balance_sheet(params=SimpleNamespace(as_of_date=datetime.utcnow()))

    assert result["total_assets"] == Decimal("500")
    assert result["total_liabilities"] == Decimal("200")
    assert result["total_equity"] == Decimal("100")


def test_trial_balance_uses_internal_account_ids():
    account = _make_account(1, AccountType.ASSET, "Cash")
    accounts = [account]
    rows = [SimpleNamespace(account_id=1, total_debit=Decimal("100"), total_credit=Decimal("40"))]

    db = MagicMock()
    account_query = MagicMock()
    account_query.all.return_value = accounts

    gl_query = MagicMock()
    gl_query.filter.return_value = gl_query
    gl_query.group_by.return_value = gl_query
    gl_query.all.return_value = rows

    def _query_side_effect(*args, **kwargs):
        if getattr(args[0], "__name__", None) == "Account":
            return account_query
        return gl_query

    db.query.side_effect = _query_side_effect

    service = ReportsService(db)
    params = SimpleNamespace(as_of_date=None, fiscal_year=None, cost_center=None, drill=False)
    result = service.get_trial_balance(params=params)

    assert result["accounts"][0]["account"] == "Account 1"
    assert result["accounts"][0]["account_id"] == 1
    assert result["total_debit"] == 100.0
    assert result["total_credit"] == 40.0


def test_cash_flow_uses_internal_account_ids():
    cash_account = _make_account(1, AccountType.ASSET, "Cash")

    db = MagicMock()
    account_query = MagicMock()
    account_query.filter.return_value = account_query
    account_query.all.return_value = [cash_account]

    sum_query = MagicMock()
    sum_query.filter.return_value = sum_query
    sum_query.scalar.side_effect = [
        Decimal("100"),  # opening_debit
        Decimal("20"),   # opening_credit
        Decimal("50"),   # period_debit
        Decimal("10"),   # period_credit
    ]

    entry_query = MagicMock()
    entry_query.filter.return_value = entry_query
    entry_query.order_by.return_value = entry_query
    entry_query.limit.return_value = entry_query
    entry_query.all.return_value = []

    def _query_side_effect(*args, **kwargs):
        if getattr(args[0], "__name__", None) == "Account":
            return account_query
        if getattr(args[0], "__name__", None) == "GLEntry":
            return entry_query
        return sum_query

    db.query.side_effect = _query_side_effect

    service = ReportsService(db)
    params = SimpleNamespace(start_date=datetime.utcnow(), end_date=datetime.utcnow(), limit=10)
    result = service.get_cash_flow(params=params)

    assert result["opening_balance"] == Decimal("80")
    assert result["net_cash_flow"] == Decimal("40")
    assert result["closing_balance"] == Decimal("120")


def test_financial_ratios_use_internal_account_ids():
    cash = _make_account(1, AccountType.ASSET, "Cash")
    payable = _make_account(2, AccountType.LIABILITY, "Payable")
    equity = _make_account(3, AccountType.EQUITY, "Equity")
    income = _make_account(4, AccountType.INCOME, "Income")
    expense = _make_account(5, AccountType.EXPENSE, "Expense")
    accounts = [cash, payable, equity, income, expense]

    db = MagicMock()
    account_query = MagicMock()
    account_query.all.return_value = accounts

    balance_rows = [
        SimpleNamespace(account_id=1, balance=Decimal("1000")),
        SimpleNamespace(account_id=2, balance=Decimal("-400")),
        SimpleNamespace(account_id=3, balance=Decimal("-200")),
    ]
    period_rows = [
        SimpleNamespace(account_id=4, debit=Decimal("0"), credit=Decimal("800")),
        SimpleNamespace(account_id=5, debit=Decimal("300"), credit=Decimal("0")),
    ]

    balance_query = MagicMock()
    balance_query.filter.return_value = balance_query
    balance_query.group_by.return_value = balance_query
    balance_query.all.return_value = balance_rows

    period_query = MagicMock()
    period_query.filter.return_value = period_query
    period_query.group_by.return_value = period_query
    period_query.all.return_value = period_rows

    call_state = {"count": 0}

    def _query_side_effect(*args, **kwargs):
        if getattr(args[0], "__name__", None) == "Account":
            return account_query
        call_state["count"] += 1
        return balance_query if call_state["count"] == 1 else period_query

    db.query.side_effect = _query_side_effect

    service = ReportsService(db)
    params = SimpleNamespace(as_of_date=date.today(), fiscal_year=None)
    result = service.get_financial_ratios(params=params)

    assert result["components"]["total_assets"] == 1000.0
    assert result["components"]["total_liabilities"] == 400.0
    assert result["components"]["total_equity"] == 200.0
