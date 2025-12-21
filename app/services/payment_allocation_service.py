"""Payment Allocation service for applying payments to documents."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Literal
from contextlib import contextmanager

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

    @contextmanager
    def _transaction(self):
        if self.db.in_transaction():
            with self.db.begin_nested():
                yield
        else:
            with self.db.begin():
                yield

    def _get_payment_for_update(self, payment_id: int, is_supplier_payment: bool):
        if is_supplier_payment:
            return self.db.query(SupplierPayment).filter(
                SupplierPayment.id == payment_id
            ).with_for_update().first()
        return self.db.query(Payment).filter(
            Payment.id == payment_id
        ).with_for_update().first()

    def _get_document_for_update(
        self,
        doc_type: str,
        doc_id: int,
    ):
        if doc_type == "invoice":
            return self.db.query(Invoice).filter(Invoice.id == doc_id).with_for_update().first()
        if doc_type == "bill":
            return self.db.query(PurchaseInvoice).filter(PurchaseInvoice.id == doc_id).with_for_update().first()
        if doc_type == "credit_note":
            return self.db.query(CreditNote).filter(CreditNote.id == doc_id).with_for_update().first()
        if doc_type == "debit_note":
            return self.db.query(DebitNote).filter(DebitNote.id == doc_id).with_for_update().first()
        return None

    def _get_outstanding_from_doc(self, doc_type: str, doc) -> Optional[Decimal]:
        if doc is None:
            return None
        if doc_type == "invoice":
            return Decimal(doc.balance) if doc.balance is not None else Decimal(doc.total_amount - doc.amount_paid)
        if doc_type == "bill":
            return Decimal(doc.outstanding_amount) if doc.outstanding_amount else Decimal(doc.grand_total - doc.paid_amount)
        if doc_type == "credit_note":
            return Decimal(doc.amount)
        if doc_type == "debit_note":
            return Decimal(doc.amount_remaining) if doc.amount_remaining else Decimal(doc.total_amount)
        return None

    def _apply_document_settlement(
        self,
        doc_type: str,
        doc,
        amount_paid: Decimal,
    ) -> None:
        if doc_type == "invoice":
            doc.amount_paid = (doc.amount_paid or Decimal("0")) + amount_paid
            doc.balance = doc.total_amount - doc.amount_paid
            if doc.balance <= 0:
                doc.status = "paid"
            elif doc.amount_paid > 0:
                doc.status = "partially_paid"
        elif doc_type == "bill":
            doc.paid_amount = (doc.paid_amount or Decimal("0")) + amount_paid
            doc.outstanding_amount = doc.grand_total - doc.paid_amount
            if doc.outstanding_amount <= 0:
                doc.status = "paid"
        elif doc_type == "debit_note":
            doc.amount_applied = (doc.amount_applied or Decimal("0")) + amount_paid
            doc.amount_remaining = doc.total_amount - doc.amount_applied
            if doc.amount_remaining <= 0:
                doc.status = "applied"

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
        with self._transaction():
            payment = self._get_payment_for_update(payment_id, is_supplier_payment)
            if not payment:
                raise PaymentAllocationError("Payment not found")

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
                try:
                    alloc_type = AllocationType(alloc_req.document_type)
                except ValueError:
                    raise PaymentAllocationError(f"Invalid document type: {alloc_req.document_type}")

                doc = self._get_document_for_update(
                    alloc_req.document_type, alloc_req.document_id
                )
                if doc is None:
                    raise PaymentAllocationError(
                        f"Document not found: {alloc_req.document_type}:{alloc_req.document_id}"
                    )

                doc_outstanding = self._get_outstanding_from_doc(alloc_req.document_type, doc)
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

                rate = allocation.conversion_rate or Decimal("1")
                allocation.base_allocated_amount = alloc_req.allocated_amount * rate
                allocation.base_discount_amount = alloc_req.discount_amount * rate
                allocation.base_write_off_amount = alloc_req.write_off_amount * rate

                allocation.exchange_gain_loss = self._calculate_fx_gain_loss(
                    allocation, alloc_req.document_type, alloc_req.document_id
                )

                self.db.add(allocation)
                created_allocations.append(allocation)

                self._apply_document_settlement(
                    alloc_req.document_type,
                    doc,
                    total_settling,
                )

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
        payment: Optional[Payment | SupplierPayment] = None
        supplier_payment: Optional[SupplierPayment] = None
        customer_payment: Optional[Payment] = None
        party_type: Literal["customer", "supplier"]
        if is_supplier_payment:
            supplier_payment = self.db.query(SupplierPayment).filter(
                SupplierPayment.id == payment_id
            ).first()
            payment = supplier_payment
            party_type = "supplier"
        else:
            customer_payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            payment = customer_payment
            party_type = "customer"

        party_id = None
        if is_supplier_payment:
            party_id = supplier_payment.supplier_id if supplier_payment else None
        else:
            party_id = customer_payment.customer_id if customer_payment else None

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
        with self._transaction():
            allocation = self.db.query(PaymentAllocation).filter(
                PaymentAllocation.id == allocation_id
            ).with_for_update().first()

            if not allocation:
                raise PaymentAllocationError("Allocation not found")

            total_settled = allocation.allocated_amount + allocation.discount_amount + allocation.write_off_amount

            doc = self._get_document_for_update(
                allocation.allocation_type.value,
                allocation.document_id,
            )
            if doc is None:
                raise PaymentAllocationError("Document not found for allocation")

            self._apply_document_settlement(
                allocation.allocation_type.value,
                doc,
                -total_settled,
            )

            if allocation.supplier_payment_id:
                payment = self._get_payment_for_update(allocation.supplier_payment_id, True)
                if payment:
                    payment.total_allocated -= allocation.allocated_amount
                    payment.unallocated_amount += allocation.allocated_amount
            elif allocation.payment_id:
                payment = self._get_payment_for_update(allocation.payment_id, False)
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
            bill_query = self.db.query(PurchaseInvoice).filter(
                PurchaseInvoice.supplier == str(party_id),  # supplier is string reference
                PurchaseInvoice.status.notin_(["paid", "cancelled"]),
            )
            if currency:
                bill_query = bill_query.filter(PurchaseInvoice.currency == currency)

            for bill in bill_query.order_by(PurchaseInvoice.posting_date).all():
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
        doc = self._get_document_for_update(doc_type, doc_id)
        if doc is None:
            return None
        return self._get_outstanding_from_doc(doc_type, doc)

    def _update_document_outstanding(
        self,
        doc_type: str,
        doc_id: int,
        amount_paid: Decimal,
    ) -> None:
        """Update the outstanding amount on a document."""
        doc = self._get_document_for_update(doc_type, doc_id)
        if doc is None:
            return
        self._apply_document_settlement(doc_type, doc, amount_paid)

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
