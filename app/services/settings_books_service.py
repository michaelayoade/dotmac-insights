"""Service layer for books settings routes."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.books_settings import BooksSettings, CurrencySettings, DocumentNumberFormat
from app.models.payment_terms import PaymentTermsTemplate
from app.models.accounting import ModeOfPayment


class SettingsBooksService:
    """Books settings coordinator for read/write operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_settings(self) -> BooksSettings:
        settings = self.db.query(BooksSettings).filter(BooksSettings.company == None).first()
        if not settings:
            settings = BooksSettings()
        return settings

    def save_settings(self, values: dict[str, Any]) -> None:
        settings = self.db.query(BooksSettings).filter(BooksSettings.company == None).first()
        if not settings:
            settings = BooksSettings()
            self.db.add(settings)

        for key, value in values.items():
            setattr(settings, key, value)

        self.db.commit()

    def list_document_formats(self) -> list[DocumentNumberFormat]:
        return self.db.query(DocumentNumberFormat).order_by(DocumentNumberFormat.document_type).all()

    def list_currencies(self) -> list[CurrencySettings]:
        return self.db.query(CurrencySettings).order_by(CurrencySettings.currency_code).all()

    def list_payment_terms(self) -> list[PaymentTermsTemplate]:
        return self.db.query(PaymentTermsTemplate).order_by(PaymentTermsTemplate.template_name).all()

    def list_payment_modes(self) -> list[ModeOfPayment]:
        return self.db.query(ModeOfPayment).order_by(ModeOfPayment.mode_of_payment).all()
