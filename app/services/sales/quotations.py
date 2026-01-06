"""Quotation service - business logic for price quotation management.

This service encapsulates quotation-related business logic:
- Core CRUD for quotations
- Line item management
- Workflow (submit, reply, expire, lose)
- Conversion to sales order
- Summary analytics

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.sales import Quotation, QuotationStatus, ERPNextLead
from app.models.party import CustomerAccount, Party
from app.utils.normalizers import normalize_phone
from app.models.document_lines import QuotationItem
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .quotation_types import (
    QuotationFilters,
    QuotationCreateData,
    QuotationUpdateData,
    QuotationLineItemData,
    QuotationLineItemUpdateData,
    OrderConversionData,
    QuotationSummary,
)

if TYPE_CHECKING:
    from app.auth import Principal
    from app.models.sales import SalesOrder


class QuotationService:
    """Service for quotation (price quote) management.

    All methods that mutate data do NOT commit.
    The caller is responsible for db.commit().
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Quotation CRUD
    # -------------------------------------------------------------------------

    def list_quotations(
        self,
        filters: Optional[QuotationFilters] = None,
        pagination: Optional[PaginationParams] = None,
        include_items: bool = False,
    ) -> PaginatedResult[Quotation]:
        """List quotations with optional filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.
            include_items: Whether to eagerly load line items.

        Returns:
            PaginatedResult containing quotations and total count.
        """
        query = scoped_query(self.db.query(Quotation), self.principal)

        if include_items:
            query = query.options(joinedload(Quotation.items))

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.outerjoin(Party, Quotation.party_id == Party.id)
                query = query.filter(
                    or_(
                        Quotation.party_name.ilike(like),
                        Quotation.customer_name.ilike(like),
                        Quotation.erpnext_id.ilike(like),
                        Party.name.ilike(like),
                        Party.legal_name.ilike(like),
                        Party.trading_name.ilike(like),
                        Party.primary_email.ilike(like),
                    )
                )

            if filters.status:
                try:
                    status_enum = QuotationStatus(filters.status.lower())
                    query = query.filter(Quotation.status == status_enum)
                except ValueError:
                    pass

            if filters.party_id:
                query = query.filter(Quotation.party_id == filters.party_id)

            if filters.party_name:
                query = query.filter(Quotation.party_name == filters.party_name)
            if filters.customer_name:
                query = query.filter(Quotation.customer_name == filters.customer_name)

            if filters.sales_partner_id:
                query = query.filter(Quotation.sales_partner_id == filters.sales_partner_id)

            if filters.territory_id:
                query = query.filter(Quotation.territory_id == filters.territory_id)

            if filters.min_value is not None:
                query = query.filter(Quotation.grand_total >= filters.min_value)

            if filters.max_value is not None:
                query = query.filter(Quotation.grand_total <= filters.max_value)

            if filters.date_from:
                query = query.filter(Quotation.transaction_date >= filters.date_from)

            if filters.date_to:
                query = query.filter(Quotation.transaction_date <= filters.date_to)

            if filters.valid_till_before:
                query = query.filter(Quotation.valid_till <= filters.valid_till_before)

            if filters.valid_till_after:
                query = query.filter(Quotation.valid_till >= filters.valid_till_after)

            if filters.source:
                query = query.filter(Quotation.source == filters.source)

            if filters.campaign:
                query = query.filter(Quotation.campaign == filters.campaign)

            if filters.company:
                query = query.filter(Quotation.company == filters.company)

        query = query.order_by(Quotation.created_at.desc())
        return paginate(query, pagination)

    def get_quotation(self, quotation_id: int, include_items: bool = True) -> Quotation:
        """Get a quotation by ID.

        Args:
            quotation_id: The quotation ID.
            include_items: Whether to eagerly load line items.

        Returns:
            The Quotation.

        Raises:
            NotFoundError: If quotation not found.
        """
        query = scoped_query(self.db.query(Quotation), self.principal)

        if include_items:
            query = query.options(joinedload(Quotation.items))

        quote = query.filter(Quotation.id == quotation_id).first()
        if not quote:
            raise NotFoundError(f"Quotation {quotation_id} not found")

        return quote

    def create_quotation(self, data: QuotationCreateData) -> Quotation:
        """Create a new quotation.

        Args:
            data: Quotation creation data.

        Returns:
            The created Quotation (not yet committed).
        """
        party_name = data.party_name
        customer_name = data.customer_name
        contact_name = data.contact_name
        contact_email = data.contact_email
        contact_phone = data.contact_phone
        billing_address = data.billing_address
        shipping_address = data.shipping_address
        billing_address_line1 = data.billing_address_line1
        billing_address_line2 = data.billing_address_line2
        billing_city = data.billing_city
        billing_state = data.billing_state
        billing_postal_code = data.billing_postal_code
        billing_country = data.billing_country
        billing_gps_lat = data.billing_gps_lat
        billing_gps_lng = data.billing_gps_lng
        shipping_address_line1 = data.shipping_address_line1
        shipping_address_line2 = data.shipping_address_line2
        shipping_city = data.shipping_city
        shipping_state = data.shipping_state
        shipping_postal_code = data.shipping_postal_code
        shipping_country = data.shipping_country
        shipping_gps_lat = data.shipping_gps_lat
        shipping_gps_lng = data.shipping_gps_lng
        party_id = None

        if data.customer_account_id:
            account = (
                self.db.query(CustomerAccount)
                .join(Party, CustomerAccount.party_id == Party.id)
                .filter(CustomerAccount.id == data.customer_account_id)
                .first()
            )
            if account and account.party:
                party = account.party
                party_name = party_name or party.name or party.legal_name or party.trading_name
                customer_name = customer_name or party_name
                contact_name = contact_name or party_name
                contact_email = contact_email or party.primary_email
                contact_phone = contact_phone or party.primary_phone
                party_id = party.id
                if party.addresses:
                    address = party.addresses[0] if isinstance(party.addresses[0], dict) else {}
                    billing_address_line1 = billing_address_line1 or address.get("address_line1") or address.get("line1") or address.get("street_1") or address.get("address")
                    billing_address_line2 = billing_address_line2 or address.get("address_line2") or address.get("line2") or address.get("street_2")
                    billing_city = billing_city or address.get("city")
                    billing_state = billing_state or address.get("state")
                    billing_postal_code = billing_postal_code or address.get("postal_code") or address.get("zip") or address.get("zip_code")
                    billing_country = billing_country or address.get("country")
                    billing_gps_lat = billing_gps_lat or address.get("gps_lat")
                    billing_gps_lng = billing_gps_lng or address.get("gps_lng")
                    shipping_address_line1 = shipping_address_line1 or billing_address_line1
                    shipping_address_line2 = shipping_address_line2 or billing_address_line2
                    shipping_city = shipping_city or billing_city
                    shipping_state = shipping_state or billing_state
                    shipping_postal_code = shipping_postal_code or billing_postal_code
                    shipping_country = shipping_country or billing_country
                    shipping_gps_lat = shipping_gps_lat or billing_gps_lat
                    shipping_gps_lng = shipping_gps_lng or billing_gps_lng

        if data.lead_id:
            lead = self.db.query(ERPNextLead).filter(ERPNextLead.id == data.lead_id).first()
            if lead:
                party_name = party_name or lead.lead_name
                customer_name = customer_name or lead.lead_name
                contact_name = contact_name or lead.lead_name
                contact_email = contact_email or lead.email_id
                contact_phone = contact_phone or lead.phone or lead.mobile_no

        if not party_name:
            raise ValidationError("Customer or lead name is required")

        phone_country = billing_country or shipping_country or "NG"
        if contact_phone:
            normalized = normalize_phone(contact_phone, country=phone_country)
            if not normalized.is_valid:
                raise ValidationError(normalized.error or "Invalid phone number")
            contact_phone = normalized.normalized

        if not billing_address and billing_address_line1:
            billing_address = self._compose_address(
                billing_address_line1,
                billing_address_line2,
                billing_city,
                billing_state,
                billing_postal_code,
                billing_country,
            )
        if not shipping_address and shipping_address_line1:
            shipping_address = self._compose_address(
                shipping_address_line1,
                shipping_address_line2,
                shipping_city,
                shipping_state,
                shipping_postal_code,
                shipping_country,
            )

        status = QuotationStatus.DRAFT
        if data.status:
            try:
                status = QuotationStatus(data.status.lower())
            except ValueError:
                raise ValidationError(f"Invalid quotation status: {data.status}")

        quote = Quotation(
            quotation_to=data.quotation_to,
            party_name=party_name,
            customer_name=customer_name or party_name,
            customer_account_id=data.customer_account_id,
            lead_id=data.lead_id,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            billing_address=billing_address,
            shipping_address=shipping_address,
            billing_address_line1=billing_address_line1,
            billing_address_line2=billing_address_line2,
            billing_city=billing_city,
            billing_state=billing_state,
            billing_postal_code=billing_postal_code,
            billing_country=billing_country,
            billing_gps_lat=billing_gps_lat,
            billing_gps_lng=billing_gps_lng,
            shipping_address_line1=shipping_address_line1,
            shipping_address_line2=shipping_address_line2,
            shipping_city=shipping_city,
            shipping_state=shipping_state,
            shipping_postal_code=shipping_postal_code,
            shipping_country=shipping_country,
            shipping_gps_lat=shipping_gps_lat,
            shipping_gps_lng=shipping_gps_lng,
            company=data.company,
            currency=data.currency,
            transaction_date=data.transaction_date or date.today(),
            valid_till=data.valid_till,
            order_type=data.order_type,
            sales_partner_id=data.sales_partner_id,
            territory_id=data.territory_id,
            source=data.source,
            campaign=data.campaign,
            status=status,
            origin_system="local",
            write_back_status="pending",
            party_id=party_id,
        )

        self.db.add(quote)
        self.db.flush()

        # Add line items
        for item_data in data.items:
            self.add_line_item(quote.id, item_data)

        self._recalculate_totals(quote)
        return quote

    def update_quotation(self, quotation_id: int, data: QuotationUpdateData) -> Quotation:
        """Update a quotation.

        Args:
            quotation_id: The quotation ID.
            data: Fields to update.

        Returns:
            The updated Quotation (not yet committed).

        Raises:
            NotFoundError: If quotation not found.
            ValidationError: If quotation is not in draft status.
        """
        quote = self.get_quotation(quotation_id, include_items=False)

        if quote.status not in (QuotationStatus.DRAFT, QuotationStatus.OPEN):
            raise ValidationError(f"Cannot update quotation in {quote.status.value} status")

        # Update simple fields
        update_fields = [
            "quotation_to", "party_name", "customer_name", "customer_account_id", "lead_id",
            "contact_name", "contact_email", "contact_phone", "billing_address", "shipping_address",
            "billing_address_line1", "billing_address_line2", "billing_city", "billing_state",
            "billing_postal_code", "billing_country", "billing_gps_lat", "billing_gps_lng",
            "shipping_address_line1", "shipping_address_line2", "shipping_city", "shipping_state",
            "shipping_postal_code", "shipping_country", "shipping_gps_lat", "shipping_gps_lng",
            "company", "currency", "transaction_date", "valid_till", "order_type",
            "sales_partner_id", "territory_id", "source", "campaign", "order_lost_reason",
        ]
        for field_name in update_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(quote, field_name, value)

        if data.status:
            try:
                quote.status = QuotationStatus(data.status.lower())
            except ValueError:
                raise ValidationError(f"Invalid quotation status: {data.status}")

        if data.contact_phone is not None:
            phone_country = quote.billing_country or quote.shipping_country or "NG"
            if data.contact_phone:
                normalized = normalize_phone(data.contact_phone, country=phone_country)
                if not normalized.is_valid:
                    raise ValidationError(normalized.error or "Invalid phone number")
                quote.contact_phone = normalized.normalized
            else:
                quote.contact_phone = None

        if data.billing_address_line1 and not data.billing_address:
            quote.billing_address = self._compose_address(
                quote.billing_address_line1,
                quote.billing_address_line2,
                quote.billing_city,
                quote.billing_state,
                quote.billing_postal_code,
                quote.billing_country,
            )
        if data.shipping_address_line1 and not data.shipping_address:
            quote.shipping_address = self._compose_address(
                quote.shipping_address_line1,
                quote.shipping_address_line2,
                quote.shipping_city,
                quote.shipping_state,
                quote.shipping_postal_code,
                quote.shipping_country,
            )

        if data.items is not None:
            self.db.query(QuotationItem).filter(QuotationItem.quotation_id == quote.id).delete()
            for item_data in data.items:
                self.add_line_item(quote.id, item_data)

        return quote

    def delete_quotation(self, quotation_id: int) -> None:
        """Soft delete a quotation.

        Args:
            quotation_id: The quotation ID.

        Raises:
            NotFoundError: If quotation not found.
            ValidationError: If quotation cannot be deleted.
        """
        quote = self.get_quotation(quotation_id, include_items=False)

        if quote.status == QuotationStatus.ORDERED:
            raise ValidationError("Cannot delete quotation that has been converted to order")

        # Soft delete using SoftDeleteMixin
        quote.soft_delete()

    # -------------------------------------------------------------------------
    # Line Item Management
    # -------------------------------------------------------------------------

    def add_line_item(self, quotation_id: int, data: QuotationLineItemData) -> QuotationItem:
        """Add a line item to a quotation.

        Args:
            quotation_id: The quotation ID.
            data: Line item data.

        Returns:
            The created QuotationItem.

        Raises:
            NotFoundError: If quotation not found.
            ValidationError: If quotation is not editable.
        """
        quote = self.get_quotation(quotation_id, include_items=False)

        if quote.status not in (QuotationStatus.DRAFT, QuotationStatus.OPEN):
            raise ValidationError(f"Cannot add items to quotation in {quote.status.value} status")

        # Calculate line amount
        amount = data.qty * data.rate
        if data.discount_percentage:
            amount = amount * (1 - data.discount_percentage / 100)
        elif data.discount_amount:
            amount = amount - data.discount_amount
        tax_amount = data.tax_amount
        if data.tax_rate and not data.tax_amount:
            tax_amount = amount * (data.tax_rate / 100)

        item = QuotationItem(
            quotation_id=quotation_id,
            item_code=data.item_code,
            item_name=data.item_name,
            description=data.description,
            qty=data.qty,
            rate=data.rate,
            uom=data.uom,
            discount_percentage=data.discount_percentage,
            discount_amount=data.discount_amount,
            amount=amount,
            net_amount=amount,
            tax_code_id=data.tax_code_id,
            tax_rate=data.tax_rate,
            tax_amount=tax_amount,
            is_tax_inclusive=data.is_tax_inclusive,
            warehouse=data.warehouse,
        )

        self.db.add(item)
        self.db.flush()

        self._recalculate_totals(quote)
        return item

    def update_line_item(self, item_id: int, data: QuotationLineItemUpdateData) -> QuotationItem:
        """Update a quotation line item.

        Args:
            item_id: The line item ID.
            data: Fields to update.

        Returns:
            The updated QuotationItem.

        Raises:
            NotFoundError: If line item not found.
        """
        item = self.db.query(QuotationItem).filter(QuotationItem.id == item_id).first()
        if not item:
            raise NotFoundError(f"Quotation item {item_id} not found")

        quote = self.get_quotation(item.quotation_id, include_items=False)
        if quote.status not in (QuotationStatus.DRAFT, QuotationStatus.OPEN):
            raise ValidationError(f"Cannot update items on quotation in {quote.status.value} status")

        # Update fields
        if data.qty is not None:
            item.qty = data.qty
        if data.rate is not None:
            item.rate = data.rate
        if data.discount_percentage is not None:
            item.discount_percentage = data.discount_percentage
        if data.discount_amount is not None:
            item.discount_amount = data.discount_amount
        if data.description is not None:
            item.description = data.description
        if data.tax_code_id is not None:
            item.tax_code_id = data.tax_code_id
        if data.tax_rate is not None:
            item.tax_rate = data.tax_rate
        if data.tax_amount is not None:
            item.tax_amount = data.tax_amount
        if data.is_tax_inclusive is not None:
            item.is_tax_inclusive = data.is_tax_inclusive

        # Recalculate amount
        amount = item.qty * item.rate
        if item.discount_percentage:
            amount = amount * (1 - item.discount_percentage / 100)
        elif item.discount_amount:
            amount = amount - item.discount_amount
        item.amount = amount
        item.net_amount = amount
        if item.tax_rate and not item.tax_amount:
            item.tax_amount = amount * (item.tax_rate / 100)

        self._recalculate_totals(quote)
        return item

    def remove_line_item(self, item_id: int) -> None:
        """Remove a line item from a quotation.

        Args:
            item_id: The line item ID.

        Raises:
            NotFoundError: If line item not found.
        """
        item = self.db.query(QuotationItem).filter(QuotationItem.id == item_id).first()
        if not item:
            raise NotFoundError(f"Quotation item {item_id} not found")

        quote = self.get_quotation(item.quotation_id, include_items=False)
        if quote.status not in (QuotationStatus.DRAFT, QuotationStatus.OPEN):
            raise ValidationError(f"Cannot remove items from quotation in {quote.status.value} status")

        self.db.delete(item)
        self.db.flush()

        self._recalculate_totals(quote)

    # -------------------------------------------------------------------------
    # Workflow Operations
    # -------------------------------------------------------------------------

    def submit_quotation(self, quotation_id: int) -> Quotation:
        """Submit a draft quotation (DRAFT → OPEN).

        Args:
            quotation_id: The quotation ID.

        Returns:
            The updated Quotation.

        Raises:
            NotFoundError: If quotation not found.
            ValidationError: If quotation cannot be submitted.
        """
        quote = self.get_quotation(quotation_id, include_items=True)

        if quote.status != QuotationStatus.DRAFT:
            raise ValidationError(f"Can only submit quotations in draft status, current: {quote.status.value}")

        if not quote.items:
            raise ValidationError("Cannot submit quotation without line items")

        quote.status = QuotationStatus.OPEN
        quote.docstatus = 1
        return quote

    def mark_replied(self, quotation_id: int) -> Quotation:
        """Mark quotation as replied (OPEN → REPLIED).

        Args:
            quotation_id: The quotation ID.

        Returns:
            The updated Quotation.
        """
        quote = self.get_quotation(quotation_id, include_items=False)

        if quote.status != QuotationStatus.OPEN:
            raise ValidationError(f"Can only mark open quotations as replied, current: {quote.status.value}")

        quote.status = QuotationStatus.REPLIED
        return quote

    def mark_lost(
        self,
        quotation_id: int,
        reason: Optional[str] = None,
        competitor: Optional[str] = None,
    ) -> Quotation:
        """Mark quotation as lost.

        Args:
            quotation_id: The quotation ID.
            reason: Optional lost reason.
            competitor: Optional competitor name.

        Returns:
            The updated Quotation.
        """
        quote = self.get_quotation(quotation_id, include_items=False)

        if quote.status in (QuotationStatus.ORDERED, QuotationStatus.CANCELLED):
            raise ValidationError(f"Cannot mark quotation as lost in {quote.status.value} status")

        quote.status = QuotationStatus.LOST
        if reason:
            quote.order_lost_reason = reason

        return quote

    def expire_quotation(self, quotation_id: int) -> Quotation:
        """Mark quotation as expired.

        Args:
            quotation_id: The quotation ID.

        Returns:
            The updated Quotation.
        """
        quote = self.get_quotation(quotation_id, include_items=False)

        if quote.status in (QuotationStatus.ORDERED, QuotationStatus.CANCELLED, QuotationStatus.LOST):
            raise ValidationError(f"Cannot expire quotation in {quote.status.value} status")

        quote.status = QuotationStatus.EXPIRED
        return quote

    def cancel_quotation(self, quotation_id: int) -> Quotation:
        """Cancel a quotation.

        Args:
            quotation_id: The quotation ID.

        Returns:
            The updated Quotation.
        """
        quote = self.get_quotation(quotation_id, include_items=False)

        if quote.status == QuotationStatus.ORDERED:
            raise ValidationError("Cannot cancel quotation that has been converted to order")

        quote.status = QuotationStatus.CANCELLED
        quote.docstatus = 2
        return quote

    # -------------------------------------------------------------------------
    # Conversion
    # -------------------------------------------------------------------------

    def convert_to_order(
        self,
        quotation_id: int,
        conversion_data: Optional[OrderConversionData] = None,
    ) -> "SalesOrder":
        """Convert quotation to sales order.

        Args:
            quotation_id: The quotation ID.
            conversion_data: Optional conversion options.

        Returns:
            The created SalesOrder.

        Raises:
            NotFoundError: If quotation not found.
            ValidationError: If quotation cannot be converted.
        """
        from app.models.sales import SalesOrder, SalesOrderStatus
        from app.models.document_lines import SalesOrderItem

        quote = self.get_quotation(quotation_id, include_items=True)

        if quote.status not in (QuotationStatus.OPEN, QuotationStatus.REPLIED):
            raise ValidationError(f"Cannot convert quotation in {quote.status.value} status")

        if not quote.items:
            raise ValidationError("Cannot convert quotation without line items")

        # Create sales order
        order = SalesOrder(
            customer=quote.party_name,
            customer_name=quote.customer_name,
            customer_account_id=quote.customer_account_id,
            contact_name=quote.contact_name,
            contact_email=quote.contact_email,
            contact_phone=quote.contact_phone,
            billing_address=quote.billing_address,
            shipping_address=quote.shipping_address,
            quotation_id=quote.id,
            company=quote.company,
            currency=quote.currency,
            transaction_date=date.today(),
            delivery_date=conversion_data.delivery_date if conversion_data else None,
            order_type=conversion_data.order_type if conversion_data else quote.order_type,
            sales_partner_id=quote.sales_partner_id,
            territory_id=quote.territory_id,
            source=quote.source,
            campaign=quote.campaign,
            status=SalesOrderStatus.DRAFT,
            # Copy totals
            total_qty=quote.total_qty,
            total=quote.total,
            net_total=quote.net_total,
            grand_total=quote.grand_total,
            rounded_total=quote.rounded_total,
            total_taxes_and_charges=quote.total_taxes_and_charges,
        )

        self.db.add(order)
        self.db.flush()

        # Copy line items
        for q_item in quote.items:
            so_item = SalesOrderItem(
                sales_order_id=order.id,
                item_code=q_item.item_code,
                item_name=q_item.item_name,
                description=q_item.description,
                qty=q_item.qty,
                rate=q_item.rate,
                amount=q_item.amount,
                uom=q_item.uom,
                discount_percentage=q_item.discount_percentage,
                discount_amount=q_item.discount_amount,
                net_amount=q_item.net_amount,
                tax_code_id=q_item.tax_code_id,
                tax_rate=q_item.tax_rate,
                tax_amount=q_item.tax_amount,
                is_tax_inclusive=q_item.is_tax_inclusive,
                warehouse=q_item.warehouse,
            )
            self.db.add(so_item)

        # Mark quotation as ordered
        quote.status = QuotationStatus.ORDERED

        return order

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_summary(self, filters: Optional[QuotationFilters] = None) -> QuotationSummary:
        """Get quotation summary statistics.

        Args:
            filters: Optional filters to apply.

        Returns:
            QuotationSummary with aggregated stats.
        """
        base_query = scoped_query(self.db.query(Quotation), self.principal)

        if filters:
            if filters.date_from:
                base_query = base_query.filter(Quotation.transaction_date >= filters.date_from)
            if filters.date_to:
                base_query = base_query.filter(Quotation.transaction_date <= filters.date_to)
            if filters.company:
                base_query = base_query.filter(Quotation.company == filters.company)

        # Total
        total = base_query.count()
        total_value = base_query.with_entities(func.sum(Quotation.grand_total)).scalar() or Decimal("0")

        # By status
        def get_status_stats(status: QuotationStatus):
            q = base_query.filter(Quotation.status == status)
            count = q.count()
            value = q.with_entities(func.sum(Quotation.grand_total)).scalar() or Decimal("0")
            return count, value

        draft_count, draft_value = get_status_stats(QuotationStatus.DRAFT)
        open_count, open_value = get_status_stats(QuotationStatus.OPEN)
        ordered_count, ordered_value = get_status_stats(QuotationStatus.ORDERED)
        lost_count, lost_value = get_status_stats(QuotationStatus.LOST)

        # Conversion rate
        closed = ordered_count + lost_count
        conversion_rate = (ordered_count / closed * 100) if closed > 0 else 0.0

        # Average
        avg_value = total_value / total if total > 0 else Decimal("0")

        return QuotationSummary(
            total_count=total,
            total_value=total_value,
            draft_count=draft_count,
            draft_value=draft_value,
            open_count=open_count,
            open_value=open_value,
            ordered_count=ordered_count,
            ordered_value=ordered_value,
            lost_count=lost_count,
            lost_value=lost_value,
            conversion_rate=conversion_rate,
            avg_quote_value=avg_value,
        )

    def get_conversion_rate(self, filters: Optional[QuotationFilters] = None) -> float:
        """Calculate quotation to order conversion rate.

        Args:
            filters: Optional filters.

        Returns:
            Conversion rate as percentage.
        """
        summary = self.get_summary(filters)
        return summary.conversion_rate

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _recalculate_totals(self, quote: Quotation) -> None:
        """Recalculate quotation totals from line items."""
        items = self.db.query(QuotationItem).filter(
            QuotationItem.quotation_id == quote.id
        ).all()

        total_qty = sum(item.qty for item in items)
        total = sum(item.amount for item in items)
        total_taxes = sum((item.tax_amount or Decimal("0")) for item in items)

        quote.total_qty = total_qty
        quote.total = total
        quote.net_total = total
        quote.total_taxes_and_charges = total_taxes
        quote.grand_total = total + total_taxes
        quote.rounded_total = round(quote.grand_total, 0)

    @staticmethod
    def _compose_address(
        line1: Optional[str],
        line2: Optional[str],
        city: Optional[str],
        state: Optional[str],
        postal_code: Optional[str],
        country: Optional[str],
    ) -> str:
        parts = [line1, line2, city, state, postal_code, country]
        return ", ".join([part for part in parts if part])
