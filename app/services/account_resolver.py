"""Account resolution helpers for posting services."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.books_settings import BooksSettings


class AccountResolver:
    """Resolve GL accounts using books settings with sensible fallbacks."""

    def __init__(self, db: Session):
        self.db = db

    def _get_books_settings(self, company: Optional[str]) -> Optional[BooksSettings]:
        if company:
            settings = self.db.query(BooksSettings).filter(
                BooksSettings.company == company
            ).first()
            if settings:
                return settings
        return self.db.query(BooksSettings).filter(
            BooksSettings.company.is_(None)
        ).first()

    def resolve_receivable_account(self, company: Optional[str]) -> str:
        settings = self._get_books_settings(company)
        return (
            settings.default_receivable_account
            if settings and settings.default_receivable_account
            else "Debtors - Company"
        )

    def resolve_payable_account(self, company: Optional[str]) -> str:
        settings = self._get_books_settings(company)
        return (
            settings.default_payable_account
            if settings and settings.default_payable_account
            else "Creditors - Company"
        )

    def resolve_income_account(self, company: Optional[str]) -> str:
        settings = self._get_books_settings(company)
        return (
            settings.default_income_account
            if settings and settings.default_income_account
            else "Sales - Company"
        )

    def resolve_expense_account(self, company: Optional[str]) -> str:
        settings = self._get_books_settings(company)
        return (
            settings.default_expense_account
            if settings and settings.default_expense_account
            else "Cost of Goods Sold - Company"
        )

    def resolve_tax_liability_account(self, company: Optional[str]) -> str:
        return "VAT - Company"

    def resolve_tax_asset_account(self, company: Optional[str]) -> str:
        return "Input VAT - Company"

    def resolve_bank_account(self, company: Optional[str]) -> str:
        return "Bank - Company"

    def resolve_sales_returns_account(self, company: Optional[str]) -> str:
        return "Sales Returns - Company"
