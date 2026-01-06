"""Supplier Service."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.accounting import PurchaseInvoice, Supplier
from app.models.party import Party, PartyRole, PartyType, SupplierAccount
from app.services.types import PaginationParams, PaginatedResult
from app.services.errors import NotFoundError, ValidationError, ConflictError

from .types import SupplierFilters, SupplierCreateData, SupplierUpdateData


class SupplierService:
    """Service for supplier management."""

    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_party_for_supplier(
        self,
        *,
        supplier_name: Optional[str],
        email: Optional[str],
        phone: Optional[str],
        party_id: Optional[int],
    ) -> Party:
        party = None
        if party_id:
            party = self.db.get(Party, party_id)

        email_norm = email.strip().lower() if email else None
        if not party and email_norm:
            party = self.db.query(Party).filter(Party.primary_email == email_norm).first()

        if not party:
            party = Party(
                type=PartyType.ORGANIZATION.value,
                name=supplier_name or None,
                emails=[],
                phones=[],
            )
            self.db.add(party)
            self.db.flush()

        if email_norm:
            emails = list(party.emails or [])
            if not any((e.get("address") or "").lower() == email_norm for e in emails):
                emails.append(
                    {
                        "address": email_norm,
                        "label": "primary",
                        "is_primary": len(emails) == 0,
                        "verified": False,
                    }
                )
                party.emails = emails

        if phone:
            phones = list(party.phones or [])
            if not any((p.get("number") or "") == phone for p in phones):
                phones.append(
                    {
                        "number": phone,
                        "label": "primary",
                        "is_primary": len(phones) == 0,
                        "can_sms": False,
                        "can_whatsapp": False,
                    }
                )
                party.phones = phones

        if not party.name and supplier_name:
            party.name = supplier_name

        has_supplier_role = (
            self.db.query(PartyRole)
            .filter(PartyRole.party_id == party.id, PartyRole.role == "supplier", PartyRole.until.is_(None))
            .first()
        )
        if not has_supplier_role:
            self.db.add(PartyRole(party_id=party.id, role="supplier"))

        return party

    def _ensure_supplier_account(
        self,
        *,
        party_id: int,
        supplier_id: int,
    ) -> SupplierAccount:
        account = (
            self.db.query(SupplierAccount)
            .filter(SupplierAccount.party_id == party_id)
            .first()
        )
        if not account:
            account = SupplierAccount(
                party_id=party_id,
                account_number=f"SUP-{supplier_id}",
                status="active",
                supplier_id=supplier_id,
                external_ids={},
            )
            self.db.add(account)
        else:
            account.supplier_id = supplier_id
        return account

    def list_suppliers(
        self,
        filters: SupplierFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[Supplier]:
        """List suppliers with filtering and pagination."""
        query = self.db.query(Supplier).filter(Supplier.disabled == False)

        if filters.search:
            query = query.filter(
                or_(
                    Supplier.supplier_name.ilike(f"%{filters.search}%"),
                    Supplier.email_id.ilike(f"%{filters.search}%"),
                )
            )

        if filters.supplier_group:
            query = query.filter(Supplier.supplier_group == filters.supplier_group)

        if filters.country:
            query = query.filter(Supplier.country == filters.country)

        total = query.count()
        suppliers = query.order_by(Supplier.supplier_name).offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(data=suppliers, total=total)

    def get_supplier(self, supplier_id: int) -> Supplier:
        """Get a supplier by ID."""
        supplier = self.db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            raise NotFoundError(f"Supplier {supplier_id} not found")
        return supplier

    def get_supplier_detail(self, supplier_id: int) -> Dict[str, Any]:
        """Get supplier with bills and summary."""
        supplier = self.get_supplier(supplier_id)

        # Get supplier's bills
        bills = self.db.query(PurchaseInvoice).filter(
            or_(
                PurchaseInvoice.supplier == supplier.erpnext_id,
                PurchaseInvoice.supplier_name == supplier.supplier_name,
            )
        ).order_by(PurchaseInvoice.posting_date.desc()).limit(20).all()

        # Calculate totals
        total_purchases = sum(float(b.grand_total) for b in bills)
        total_outstanding = sum(float(b.outstanding_amount) for b in bills if b.outstanding_amount > 0)

        return {
            "supplier": supplier,
            "bills": bills,
            "total_purchases": Decimal(str(total_purchases)),
            "total_outstanding": Decimal(str(total_outstanding)),
            "bill_count": len(bills),
        }

    def create_supplier(self, data: SupplierCreateData) -> Supplier:
        """Create a new supplier."""
        # Check for duplicate
        existing = self.db.query(Supplier).filter(
            Supplier.supplier_name == data.supplier_name,
            Supplier.disabled == False,
        ).first()
        if existing:
            raise ConflictError("Supplier with this name already exists")

        supplier = Supplier(
            supplier_name=data.supplier_name,
            supplier_group=data.supplier_group,
            supplier_type=data.supplier_type,
            country=data.country,
            default_currency=data.default_currency or "NGN",
            email_id=data.email_id,
            mobile_no=data.mobile_no,
            tax_id=data.tax_id,
            payment_terms=data.payment_terms,
            disabled=False,
        )
        self.db.add(supplier)
        self.db.flush()
        party = self._get_or_create_party_for_supplier(
            supplier_name=supplier.supplier_name,
            email=supplier.email_id,
            phone=supplier.mobile_no,
            party_id=supplier.party_id,
        )
        supplier.party_id = party.id
        self._ensure_supplier_account(party_id=party.id, supplier_id=supplier.id)
        return supplier

    def update_supplier(self, supplier_id: int, data: SupplierUpdateData) -> Supplier:
        """Update a supplier."""
        supplier = self.get_supplier(supplier_id)

        # Check for duplicate name if updating name
        if data.supplier_name and data.supplier_name != supplier.supplier_name:
            existing = self.db.query(Supplier).filter(
                Supplier.supplier_name == data.supplier_name,
                Supplier.id != supplier_id,
                Supplier.disabled == False,
            ).first()
            if existing:
                raise ConflictError("Supplier with this name already exists")

        # Apply updates
        update_fields = [
            'supplier_name', 'supplier_group', 'supplier_type', 'country',
            'default_currency', 'email_id', 'mobile_no', 'tax_id',
            'payment_terms', 'disabled',
        ]

        for field_name in update_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(supplier, field_name, value)

        party = self._get_or_create_party_for_supplier(
            supplier_name=supplier.supplier_name,
            email=supplier.email_id,
            phone=supplier.mobile_no,
            party_id=supplier.party_id,
        )
        supplier.party_id = party.id
        self._ensure_supplier_account(party_id=party.id, supplier_id=supplier.id)

        self.db.flush()
        return supplier

    def delete_supplier(self, supplier_id: int, soft: bool = True) -> None:
        """Delete a supplier (soft delete by default)."""
        supplier = self.get_supplier(supplier_id)

        if soft:
            supplier.disabled = True
            self.db.flush()
        else:
            self.db.delete(supplier)
            self.db.flush()

    def get_supplier_groups(self) -> List[Dict[str, Any]]:
        """Get supplier group breakdown with counts."""
        groups = self.db.query(
            Supplier.supplier_group,
            func.count(Supplier.id).label("count"),
        ).filter(
            Supplier.disabled == False,
        ).group_by(
            Supplier.supplier_group
        ).all()

        # Get outstanding by group
        result = []
        for group_name, count in groups:
            outstanding = Decimal("0")
            if group_name:
                suppliers_in_group = self.db.query(Supplier.erpnext_id).filter(
                    Supplier.supplier_group == group_name
                ).all()
                supplier_ids = [s[0] for s in suppliers_in_group if s[0]]

                if supplier_ids:
                    total = self.db.query(
                        func.sum(PurchaseInvoice.outstanding_amount)
                    ).filter(
                        PurchaseInvoice.supplier.in_(supplier_ids),
                        PurchaseInvoice.outstanding_amount > 0,
                    ).scalar()
                    outstanding = Decimal(str(total or 0))

            result.append({
                "name": group_name or "Ungrouped",
                "count": count,
                "outstanding": outstanding,
            })

        return result

    def get_outstanding_by_supplier(self) -> Dict[str, Decimal]:
        """Get outstanding amounts indexed by supplier."""
        results = self.db.query(
            PurchaseInvoice.supplier,
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
        ).filter(
            PurchaseInvoice.outstanding_amount > 0,
        ).group_by(PurchaseInvoice.supplier).all()

        return {row.supplier: Decimal(str(row.outstanding)) for row in results if row.supplier}
