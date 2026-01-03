"""Tax Calculator service for line-level and document-level tax calculations."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP
from typing import List, Optional, cast

from sqlalchemy.orm import Session

from app.models.tax import TaxCode, RoundingMethod


@dataclass
class TaxResult:
    """Result of a tax calculation for a single line."""
    net_amount: Decimal
    tax_amount: Decimal
    gross_amount: Decimal
    tax_rate: Decimal
    is_inclusive: bool


@dataclass
class TaxSummary:
    """Summary of taxes for a document."""
    total_net: Decimal
    total_tax: Decimal
    total_gross: Decimal
    tax_breakdown: List[dict]  # List of {tax_code, tax_rate, base_amount, tax_amount}


class TaxCalculator:
    """
    Service for calculating taxes on document lines and documents.

    Supports:
    - Inclusive and exclusive tax calculation
    - Multiple rounding methods (round, floor, ceil)
    - Configurable precision
    """

    def __init__(self, db: Session):
        self.db = db

    def get_tax_code(self, tax_code_id: int) -> Optional[TaxCode]:
        """Get a tax code by ID."""
        return self.db.query(TaxCode).filter(TaxCode.id == tax_code_id).first()

    def calculate_line_tax(
        self,
        amount: Decimal,
        tax_code_id: Optional[int] = None,
        tax_rate: Optional[Decimal] = None,
        is_inclusive: Optional[bool] = None,
        rounding_method: RoundingMethod = RoundingMethod.ROUND,
        precision: int = 2,
    ) -> TaxResult:
        """
        Calculate tax for a single line item.

        Args:
            amount: The line amount (gross if inclusive, net if exclusive)
            tax_code_id: ID of the tax code to use (overrides tax_rate/is_inclusive)
            tax_rate: Tax rate percentage (used if tax_code_id not provided)
            is_inclusive: Whether amount includes tax (used if tax_code_id not provided)
            rounding_method: How to round the tax amount
            precision: Decimal places for rounding

        Returns:
            TaxResult with calculated amounts
        """
        # Get settings from tax code if provided
        if tax_code_id:
            tax_code = self.get_tax_code(tax_code_id)
            if tax_code:
                tax_rate = tax_code.rate
                is_inclusive = tax_code.is_tax_inclusive
                rounding_method = tax_code.rounding_method
                precision = tax_code.rounding_precision

        # Default values
        if tax_rate is None:
            tax_rate = Decimal("0")
        if is_inclusive is None:
            is_inclusive = False

        # Ensure amount is Decimal
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        if not isinstance(tax_rate, Decimal):
            tax_rate = Decimal(str(tax_rate))

        # Calculate tax
        if is_inclusive:
            # Amount includes tax - extract it
            # gross = net + (net * rate / 100)
            # gross = net * (1 + rate/100)
            # net = gross / (1 + rate/100)
            divisor = Decimal("1") + (tax_rate / Decimal("100"))
            net_amount = amount / divisor
            tax_amount = amount - net_amount
            gross_amount = amount
        else:
            # Amount is net - add tax
            net_amount = amount
            tax_amount = amount * tax_rate / Decimal("100")
            gross_amount = net_amount + tax_amount

        # Round tax amount
        tax_amount = self._round_amount(tax_amount, rounding_method, precision)

        # Recalculate gross after rounding
        if is_inclusive:
            net_amount = gross_amount - tax_amount
        else:
            gross_amount = net_amount + tax_amount

        # Round net amount
        net_amount = self._round_amount(net_amount, rounding_method, precision)

        return TaxResult(
            net_amount=net_amount,
            tax_amount=tax_amount,
            gross_amount=gross_amount,
            tax_rate=tax_rate,
            is_inclusive=is_inclusive,
        )

    def calculate_document_taxes(
        self,
        lines: List[dict],
        default_tax_code_id: Optional[int] = None,
    ) -> TaxSummary:
        """
        Calculate total taxes for a document from its lines.

        Args:
            lines: List of line dicts with keys:
                - amount: Line amount
                - tax_code_id (optional): Tax code for this line
                - tax_rate (optional): Override tax rate
                - is_tax_inclusive (optional): Override inclusive flag
            default_tax_code_id: Default tax code if line doesn't specify one

        Returns:
            TaxSummary with totals and breakdown
        """
        total_net = Decimal("0")
        total_tax = Decimal("0")
        total_gross = Decimal("0")
        tax_breakdown = {}

        for line in lines:
            amount = Decimal(str(line.get("amount", 0)))
            tax_code_id = line.get("tax_code_id") or default_tax_code_id
            tax_rate = line.get("tax_rate")
            is_inclusive = line.get("is_tax_inclusive")

            if tax_rate is not None:
                tax_rate = Decimal(str(tax_rate))

            result = self.calculate_line_tax(
                amount=amount,
                tax_code_id=tax_code_id,
                tax_rate=tax_rate,
                is_inclusive=is_inclusive,
            )

            total_net += result.net_amount
            total_tax += result.tax_amount
            total_gross += result.gross_amount

            # Build breakdown by tax rate
            rate_key = str(result.tax_rate)
            if rate_key not in tax_breakdown:
                tax_breakdown[rate_key] = {
                    "tax_code_id": tax_code_id,
                    "tax_rate": result.tax_rate,
                    "base_amount": Decimal("0"),
                    "tax_amount": Decimal("0"),
                }
            base_amount = cast(Decimal, tax_breakdown[rate_key]["base_amount"])
            tax_amount = cast(Decimal, tax_breakdown[rate_key]["tax_amount"])
            tax_breakdown[rate_key]["base_amount"] = base_amount + result.net_amount
            tax_breakdown[rate_key]["tax_amount"] = tax_amount + result.tax_amount

        return TaxSummary(
            total_net=total_net,
            total_tax=total_tax,
            total_gross=total_gross,
            tax_breakdown=list(tax_breakdown.values()),
        )

    def _round_amount(
        self,
        amount: Decimal,
        method: RoundingMethod,
        precision: int,
    ) -> Decimal:
        """Round an amount using the specified method and precision."""
        quantize_exp = Decimal(10) ** -precision

        if method == RoundingMethod.ROUND:
            return amount.quantize(quantize_exp, rounding=ROUND_HALF_UP)
        elif method == RoundingMethod.FLOOR:
            return amount.quantize(quantize_exp, rounding=ROUND_DOWN)
        elif method == RoundingMethod.CEIL:
            return amount.quantize(quantize_exp, rounding=ROUND_UP)
        else:
            return amount.quantize(quantize_exp, rounding=ROUND_HALF_UP)

    def round_tax_amount(
        self,
        amount: Decimal,
        tax_code_id: Optional[int] = None,
    ) -> Decimal:
        """Round a tax amount using the tax code's settings."""
        method = RoundingMethod.ROUND
        precision = 2

        if tax_code_id:
            tax_code = self.get_tax_code(tax_code_id)
            if tax_code:
                method = tax_code.rounding_method
                precision = tax_code.rounding_precision

        return self._round_amount(amount, method, precision)
