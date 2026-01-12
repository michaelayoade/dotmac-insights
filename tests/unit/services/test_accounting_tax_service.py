"""Tests for tax service payment edge cases."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.tax import TaxFilingStatus
from app.services.accounting.tax_service import TaxService
from app.services.accounting.tax_types import TaxPaymentCreateData
from app.services.errors import ValidationError


def _mock_period(status: TaxFilingStatus, tax_amount: Decimal, amount_paid: Decimal):
    return SimpleNamespace(
        status=status,
        tax_amount=tax_amount,
        amount_paid=amount_paid,
    )


def test_record_payment_rejects_overpayment(monkeypatch):
    db = MagicMock()
    service = TaxService(db)
    period = _mock_period(TaxFilingStatus.OPEN, Decimal("100"), Decimal("60"))
    monkeypatch.setattr(service, "get_filing_period", lambda period_id: period)

    monkeypatch.setattr(
        "app.services.accounting.tax_service.SoftValidationService",
        lambda _db: SimpleNamespace(validate_and_store=lambda *_args, **_kwargs: None),
    )

    payment = TaxPaymentCreateData(
        payment_date=date.today(),
        amount=Decimal("50"),
        payment_reference="PAY-1",
        payment_method="transfer",
        bank_account="BANK-1",
    )

    with pytest.raises(ValidationError):
        service.record_payment(1, payment)


def test_record_payment_rejects_paid_period(monkeypatch):
    db = MagicMock()
    service = TaxService(db)
    period = _mock_period(TaxFilingStatus.PAID, Decimal("100"), Decimal("100"))
    monkeypatch.setattr(service, "get_filing_period", lambda period_id: period)

    payment = TaxPaymentCreateData(
        payment_date=date.today(),
        amount=Decimal("10"),
        payment_reference="PAY-2",
        payment_method="transfer",
        bank_account="BANK-1",
    )

    with pytest.raises(ValidationError):
        service.record_payment(1, payment)


def test_record_payment_rejects_non_positive_amount(monkeypatch):
    db = MagicMock()
    service = TaxService(db)
    period = _mock_period(TaxFilingStatus.OPEN, Decimal("100"), Decimal("0"))
    monkeypatch.setattr(service, "get_filing_period", lambda period_id: period)

    payment = TaxPaymentCreateData(
        payment_date=date.today(),
        amount=Decimal("0"),
        payment_reference="PAY-3",
        payment_method="transfer",
        bank_account="BANK-1",
    )

    with pytest.raises(ValidationError):
        service.record_payment(1, payment)


def test_record_payment_marks_paid(monkeypatch):
    db = MagicMock()
    service = TaxService(db)
    period = _mock_period(TaxFilingStatus.OPEN, Decimal("100"), Decimal("0"))
    monkeypatch.setattr(service, "get_filing_period", lambda period_id: period)

    monkeypatch.setattr(
        "app.services.accounting.tax_service.SoftValidationService",
        lambda _db: SimpleNamespace(validate_and_store=lambda *_args, **_kwargs: None),
    )

    payment = TaxPaymentCreateData(
        payment_date=date.today(),
        amount=Decimal("100"),
        payment_reference="PAY-4",
        payment_method="transfer",
        bank_account="BANK-1",
    )

    service.record_payment(1, payment)

    assert period.amount_paid == Decimal("100")
    assert period.status == TaxFilingStatus.PAID
