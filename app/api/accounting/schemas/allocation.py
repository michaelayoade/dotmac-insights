"""Shared payment allocation schemas for AP and AR payments."""
from typing import Optional

from pydantic import BaseModel


class AllocationCreate(BaseModel):
    """Schema for creating a payment allocation.

    Used by both AP payments (bills, debit notes) and AR payments (invoices, credit notes).
    """

    document_type: str  # AP: bill, debit_note | AR: invoice, credit_note
    document_id: int
    allocated_amount: float
    discount_amount: float = 0
    write_off_amount: float = 0
    discount_type: Optional[str] = None
    discount_account: Optional[str] = None
    write_off_account: Optional[str] = None
    write_off_reason: Optional[str] = None
