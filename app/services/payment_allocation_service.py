"""Payment Allocation service for applying payments to documents."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Literal

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.supplier_payment import SupplierPayment
from app.models.payment_allocation import PaymentAllocation, AllocationType, DiscountType
from app.models.invoice import Invoice
from app.models.accounting import PurchaseInvoice
from app.models.credit_note import CreditNote
from app.models.books_settings import DebitNote


@dataclass
class AllocationRequest:
    """Request to allocate a payment to a document."""
    document_type: str  # invoice, bill, credit_note, debit_note
    document_id: int
    allocated_amount: Decimal
    discount_amount: Decimal = Decimal("0")
    write_off_amount: Decimal = Decimal("0")
    discount_type: Optional[str] = None
    discount_account: Optional[str] = None
    write_off_account: Optional[str] = None
    write_off_reason: Optional[str] = None


@dataclass
class OutstandingDocument:
    """An outstanding document available for payment."""
    document_type: str
    document_id: int
    document_number: str
    document_date: str
    due_date: Optional[str]
    currency: str
    total_amount: Decimal
    outstanding_amount: Decimal
    party_name: Optional[str]


class PaymentAllocationError(Exception):
    """Error during payment allocation."""
    pass


class PaymentAllocationService:
    """
    Service for allocating payments to invoices, bills, and notes.

    Supports:
    - Manual allocation to specific documents
    - Auto-allocation using FIFO (oldest first)
    - Discount and write-off handling
    - FX gain/loss calculation
    """

    def __init__(self, db: Session):
        self.db = db

    def allocate_payment(
        self,
        payment_id: int,
        allocations: List[AllocationRequest],
        user_id: Optional[int] = None,
        is_supplier_payment: bool = False,
    ) -> List[PaymentAllocation]:
        """
        Allocate a payment to one or more documents.

        Args:
            payment_id: ID of the payment (Payment or SupplierPayment)
            allocations: List of allocation requests
            user_id: ID of user performing allocation
            is_supplier_payment: True if this is a supplier payment

        Returns:
            List of created PaymentAllocation records
        """
        # Get payment
        if is_supplier_payment:
            payment = self.db.query(SupplierPayment).filter(
                SupplierPayment.id == payment_id
            ).first()
        else:
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()

        if not payment:
            raise PaymentAllocationError("Payment not found")

        # Check available amount
        available = getattr(payment, "unallocated_amount", Decimal("0"))
        if available is None:
            available = payment.amount if hasattr(payment, "amount") else payment.paid_amount

        total_allocating = sum(a.allocated_amount for a in allocations)
        if total_allocating > available:
            raise PaymentAllocationError(
                f"Allocation total ({total_allocating}) exceeds available amount ({available})"
            )

        created_allocations = []

        for alloc_req in allocations:
            # Map document type to enum
            try:
                alloc_type = AllocationType(alloc_req.document_type)
            except ValueError:
                raise PaymentAllocationError(f"Invalid document type: {alloc_req.document_type}")

            # Verify document exists and get outstanding
            doc_outstanding = self._get_document_outstanding(
                alloc_req.document_type, alloc_req.document_id
            )
            if doc_outstanding is None:
                raise PaymentAllocationError(
                    f"Document not found: {alloc_req.document_type}:{alloc_req.document_id}"
                )

            total_settling = (
                alloc_req.allocated_amount +
                alloc_req.discount_amount +
                alloc_req.write_off_amount
            )
            if total_settling > doc_outstanding:
                raise PaymentAllocationError(
                    f"Settlement amount ({total_settling}) exceeds outstanding ({doc_outstanding})"
                )

            # Create allocation
            allocation = PaymentAllocation(
                payment_id=None if is_supplier_payment else payment_id,
                supplier_payment_id=payment_id if is_supplier_payment else None,
                allocation_type=alloc_type,
                document_id=alloc_req.document_id,
                allocated_amount=alloc_req.allocated_amount,
                discount_amount=alloc_req.discount_amount,
                write_off_amount=alloc_req.write_off_amount,
                conversion_rate=getattr(payment, "conversion_rate", Decimal("1")),
                discount_type=DiscountType(alloc_req.discount_type) if alloc_req.discount_type else None,
                discount_account=alloc_req.discount_account,
                write_off_account=alloc_req.write_off_account,
                write_off_reason=alloc_req.write_off_reason,
                created_by_id=user_id,
            )

            # Calculate base amounts
            rate = allocation.conversion_rate or Decimal("1")
            allocation.base_allocated_amount = alloc_req.allocated_amount * rate
            allocation.base_discount_amount = alloc_req.discount_amount * rate
            allocation.base_write_off_amount = alloc_req.write_off_amount * rate

            # Calculate FX gain/loss if needed
            allocation.exchange_gain_loss = self._calculate_fx_gain_loss(
                allocation, alloc_req.document_type, alloc_req.document_id
            )

            self.db.add(allocation)
            created_allocations.append(allocation)

            # Update document outstanding
            self._update_document_outstanding(
                alloc_req.document_type,
                alloc_req.document_id,
                total_settling,
            )

        # Update payment totals
        if is_supplier_payment:
            payment.total_allocated = (payment.total_allocated or Decimal("0")) + total_allocating
            payment.unallocated_amount = payment.paid_amount - payment.total_allocated
        else:
            payment.total_allocated = (payment.total_allocated or Decimal("0")) + total_allocating
            payment.unallocated_amount = payment.amount - payment.total_allocated

        return created_allocations

    def auto_allocate(
        self,
        payment_id: int,
        is_supplier_payment: bool = False,
        user_id: Optional[int] = None,
    ) -> List[PaymentAllocation]:
        """
        Auto-allocate a payment using FIFO (oldest first).

        Args:
            payment_id: ID of the payment
            is_supplier_payment: True if this is a supplier payment
            user_id: ID of user performing allocation

        Returns:
            List of created PaymentAllocation records
        """
        # Get payment and party
        if is_supplier_payment:
            payment = self.db.query(SupplierPayment).filter(
                SupplierPayment.id == payment_id
            ).first()
            party_id = payment.supplier_id if payment else None
            party_type = "supplier"
        else:
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            party_id = payment.customer_id if payment else None
            party_type = "customer"

        if not payment or not party_id:
            raise PaymentAllocationError("Payment not found or no party linked")

        available = getattr(payment, "unallocated_amount", None)
        if available is None:
            available = payment.amount if hasattr(payment, "amount") else payment.paid_amount

        if available <= 0:
            return []

        # Get outstanding documents for this party
        docs = self.get_outstanding_documents(party_type, party_id)

        # Build allocation requests in FIFO order
        alloc_requests = []
        remaining = available

        for doc in docs:
            if remaining <= 0:
                break

            alloc_amount = min(remaining, doc.outstanding_amount)
            alloc_requests.append(
                AllocationRequest(
                    document_type=doc.document_type,
                    document_id=doc.document_id,
                    allocated_amount=alloc_amount,
                )
            )
            remaining -= alloc_amount

        if not alloc_requests:
            return []

        return self.allocate_payment(
            payment_id=payment_id,
            allocations=alloc_requests,
            user_id=user_id,
            is_supplier_payment=is_supplier_payment,
        )

    def remove_allocation(
        self,
        allocation_id: int,
        user_id: Optional[int] = None,
    ) -> None:
        """
        Remove a payment allocation.

        Args:
            allocation_id: ID of the allocation to remove
            user_id: ID of user removing allocation
        """
        allocation = self.db.query(PaymentAllocation).filter(
            PaymentAllocation.id == allocation_id
        ).first()

        if not allocation:
            raise PaymentAllocationError("Allocation not found")

        # Restore document outstanding
        total_settled = allocation.allocated_amount + allocation.discount_amount + allocation.write_off_amount
        self._update_document_outstanding(
            allocation.allocation_type.value,
            allocation.document_id,
            -total_settled,  # Negative to restore
        )

        # Restore payment available
        if allocation.supplier_payment_id:
            payment = self.db.query(SupplierPayment).filter(
                SupplierPayment.id == allocation.supplier_payment_id
            ).first()
            if payment:
                payment.total_allocated -= allocation.allocated_amount
                payment.unallocated_amount += allocation.allocated_amount
        elif allocation.payment_id:
            payment = self.db.query(Payment).filter(
                Payment.id == allocation.payment_id
            ).first()
            if payment:
                payment.total_allocated -= allocation.allocated_amount
                payment.unallocated_amount += allocation.allocated_amount

        self.db.delete(allocation)

    def get_outstanding_documents(
        self,
        party_type: Literal["customer", "supplier"],
        party_id: int,
        currency: Optional[str] = None,
    ) -> List[OutstandingDocument]:
        """
        Get outstanding documents for a party.

        Args:
            party_type: "customer" or "supplier"
            party_id: ID of the customer or supplier
            currency: Filter by currency (optional)

        Returns:
            List of OutstandingDocument sorted by date (oldest first)
        """
        docs = []

        if party_type == "customer":
            # Get outstanding invoices
            query = self.db.query(Invoice).filter(
                Invoice.customer_id == party_id,
                Invoice.status.notin_(["paid", "cancelled", "refunded"]),
            )
            if currency:
                query = query.filter(Invoice.currency == currency)

            for inv in query.order_by(Invoice.invoice_date).all():
                outstanding = inv.balance if inv.balance else (inv.total_amount - inv.amount_paid)
                if outstanding > 0:
                    docs.append(OutstandingDocument(
                        document_type="invoice",
                        document_id=inv.id,
                        document_number=inv.invoice_number or "",
                        document_date=inv.invoice_date.isoformat() if inv.invoice_date else "",
                        due_date=inv.due_date.isoformat() if inv.due_date else None,
                        currency=inv.currency,
                        total_amount=inv.total_amount,
                        outstanding_amount=outstanding,
                        party_name=None,
                    ))

        elif party_type == "supplier":
            # Get outstanding bills
            query = self.db.query(PurchaseInvoice).filter(
                PurchaseInvoice.supplier == str(party_id),  # supplier is string reference
                PurchaseInvoice.status.notin_(["paid", "cancelled"]),
            )
            if currency:
                query = query.filter(PurchaseInvoice.currency == currency)

            for bill in query.order_by(PurchaseInvoice.posting_date).all():
                outstanding = bill.outstanding_amount or (bill.grand_total - bill.paid_amount)
                if outstanding > 0:
                    docs.append(OutstandingDocument(
                        document_type="bill",
                        document_id=bill.id,
                        document_number=bill.erpnext_id or "",
                        document_date=bill.posting_date.isoformat() if bill.posting_date else "",
                        due_date=bill.due_date.isoformat() if bill.due_date else None,
                        currency=bill.currency,
                        total_amount=bill.grand_total,
                        outstanding_amount=outstanding,
                        party_name=bill.supplier_name,
                    ))

        return docs

    def _get_document_outstanding(
        self,
        doc_type: str,
        doc_id: int,
    ) -> Optional[Decimal]:
        """Get the outstanding amount for a document."""
        if doc_type == "invoice":
            inv = self.db.query(Invoice).filter(Invoice.id == doc_id).first()
            if inv:
                return inv.balance if inv.balance else (inv.total_amount - inv.amount_paid)
        elif doc_type == "bill":
            bill = self.db.query(PurchaseInvoice).filter(PurchaseInvoice.id == doc_id).first()
            if bill:
                return bill.outstanding_amount or (bill.grand_total - bill.paid_amount)
        elif doc_type == "credit_note":
            cn = self.db.query(CreditNote).filter(CreditNote.id == doc_id).first()
            if cn:
                return cn.amount  # Credit notes are typically fully outstanding until applied
        elif doc_type == "debit_note":
            dn = self.db.query(DebitNote).filter(DebitNote.id == doc_id).first()
            if dn:
                return dn.amount_remaining or dn.total_amount
        return None

    def _update_document_outstanding(
        self,
        doc_type: str,
        doc_id: int,
        amount_paid: Decimal,
    ) -> None:
        """Update the outstanding amount on a document."""
        if doc_type == "invoice":
            inv = self.db.query(Invoice).filter(Invoice.id == doc_id).first()
            if inv:
                inv.amount_paid = (inv.amount_paid or Decimal("0")) + amount_paid
                inv.balance = inv.total_amount - inv.amount_paid
                if inv.balance <= 0:
                    inv.status = "paid"
                elif inv.amount_paid > 0:
                    inv.status = "partially_paid"
        elif doc_type == "bill":
            bill = self.db.query(PurchaseInvoice).filter(PurchaseInvoice.id == doc_id).first()
            if bill:
                bill.paid_amount = (bill.paid_amount or Decimal("0")) + amount_paid
                bill.outstanding_amount = bill.grand_total - bill.paid_amount
                if bill.outstanding_amount <= 0:
                    bill.status = "paid"
        elif doc_type == "debit_note":
            dn = self.db.query(DebitNote).filter(DebitNote.id == doc_id).first()
            if dn:
                dn.amount_applied = (dn.amount_applied or Decimal("0")) + amount_paid
                dn.amount_remaining = dn.total_amount - dn.amount_applied
                if dn.amount_remaining <= 0:
                    dn.status = "applied"

    def _calculate_fx_gain_loss(
        self,
        allocation: PaymentAllocation,
        doc_type: str,
        doc_id: int,
    ) -> Decimal:
        """
        Calculate FX gain/loss for an allocation.

        This compares the document rate to the payment rate.
        """
        payment_rate = allocation.conversion_rate or Decimal("1")

        # Get document rate
        doc_rate = Decimal("1")
        if doc_type == "invoice":
            inv = self.db.query(Invoice).filter(Invoice.id == doc_id).first()
            if inv and hasattr(inv, "conversion_rate"):
                doc_rate = inv.conversion_rate or Decimal("1")
        elif doc_type == "bill":
            bill = self.db.query(PurchaseInvoice).filter(PurchaseInvoice.id == doc_id).first()
            if bill and hasattr(bill, "conversion_rate"):
                doc_rate = bill.conversion_rate or Decimal("1")

        if payment_rate == doc_rate:
            return Decimal("0")

        # FX gain/loss = allocated_amount * (payment_rate - doc_rate)
        return allocation.allocated_amount * (payment_rate - doc_rate)
