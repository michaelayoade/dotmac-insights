"""Sales sync functions for ERPNext.

This module handles syncing of sales-related entities:
- Customers, Customer Groups
- Territories, Sales Persons
- Leads, Quotations, Sales Orders
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
import structlog

from app.models.customer import Customer
from app.models.sales import (
    CustomerGroup,
    ERPNextLead,
    ERPNextLeadStatus,
    Quotation,
    QuotationStatus,
    SalesOrder,
    SalesOrderStatus,
    SalesPerson,
    Territory,
)

if TYPE_CHECKING:
    from app.sync.erpnext import ERPNextSync

logger = structlog.get_logger()


async def sync_customers(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync customers from ERPNext (to match with Splynx customers).

    Uses custom_splynx_id for primary matching, then email, then creates new.
    """
    sync_client.start_sync("customers", "full" if full_sync else "incremental")

    try:
        # Get incremental filter if not doing full sync
        filters = sync_client._get_incremental_filter("customers", full_sync)

        # Fetch all fields including custom fields
        customers = await sync_client._fetch_all_doctype(
            client,
            "Customer",
            fields=["*"],
            filters=filters,
        )

        # Pre-fetch existing customers by splynx_id for efficient matching
        customers_by_splynx_id = {
            c.splynx_id: c
            for c in sync_client.db.query(Customer).filter(Customer.splynx_id.isnot(None)).all()
        }

        batch_size = 500
        for i, cust_data in enumerate(customers, 1):
            erpnext_id = cust_data.get("name")
            custom_splynx_id = cust_data.get("custom_splynx_id")

            # Convert splynx_id to int if present
            splynx_id = None
            if custom_splynx_id:
                try:
                    splynx_id = int(custom_splynx_id)
                except (ValueError, TypeError):
                    pass

            existing = None

            # Priority 1: Match by erpnext_id
            existing = sync_client.db.query(Customer).filter(
                Customer.erpnext_id == erpnext_id
            ).first()

            # Priority 2: Match by splynx_id from ERPNext custom field
            if not existing and splynx_id:
                existing = customers_by_splynx_id.get(splynx_id)

            # Priority 3: Match by email
            if not existing:
                email = cust_data.get("email_id")
                if email:
                    existing = sync_client.db.query(Customer).filter(
                        Customer.email == email
                    ).first()

            if existing:
                # Update existing customer with ERPNext data
                existing.erpnext_id = erpnext_id

                # Update fields from ERPNext if not already set from Splynx
                if not existing.name or existing.name == "":
                    existing.name = cust_data.get("customer_name", "")
                if not existing.email:
                    existing.email = cust_data.get("email_id")
                if not existing.phone:
                    existing.phone = cust_data.get("mobile_no") or cust_data.get("custom_phone_numbers")

                # Update custom fields
                if cust_data.get("custom_gps") and not existing.gps:
                    existing.gps = cust_data.get("custom_gps")
                if cust_data.get("custom_city") and not existing.city:
                    existing.city = cust_data.get("custom_city")
                if cust_data.get("custom_region") and not existing.state:
                    existing.state = cust_data.get("custom_region")
                if cust_data.get("custom_building_type") and not existing.building_type:
                    existing.building_type = cust_data.get("custom_building_type")
                if cust_data.get("custom_notes") and not existing.notes:
                    existing.notes = cust_data.get("custom_notes")

                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                # Create new customer record with all available data
                customer = Customer(
                    erpnext_id=erpnext_id,
                    splynx_id=splynx_id,
                    name=cust_data.get("customer_name", ""),
                    email=cust_data.get("email_id"),
                    phone=cust_data.get("mobile_no") or cust_data.get("custom_phone_numbers"),
                    gps=cust_data.get("custom_gps"),
                    city=cust_data.get("custom_city"),
                    state=cust_data.get("custom_region"),
                    building_type=cust_data.get("custom_building_type"),
                    notes=cust_data.get("custom_notes"),
                )
                sync_client.db.add(customer)
                if splynx_id:
                    customers_by_splynx_id[splynx_id] = customer
                sync_client.increment_created()

            # Batch commit
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("erpnext_customers_batch_committed", processed=i, total=len(customers))

        sync_client.db.commit()
        sync_client._update_sync_cursor("customers", customers, len(customers))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_customer_groups(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync customer groups from ERPNext."""
    sync_client.start_sync("customer_groups", "full" if full_sync else "incremental")

    try:
        groups = await sync_client._fetch_all_doctype(
            client,
            "Customer Group",
            fields=["*"],
        )

        for group_data in groups:
            erpnext_id = group_data.get("name")
            existing = sync_client.db.query(CustomerGroup).filter(
                CustomerGroup.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.customer_group_name = group_data.get("customer_group_name") or str(erpnext_id or "")
                existing.parent_customer_group = group_data.get("parent_customer_group")
                existing.is_group = group_data.get("is_group", 0) == 1
                existing.default_price_list = group_data.get("default_price_list")
                existing.default_payment_terms_template = group_data.get("default_payment_terms_template")
                existing.lft = group_data.get("lft")
                existing.rgt = group_data.get("rgt")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                customer_group = CustomerGroup(
                    erpnext_id=erpnext_id,
                    customer_group_name=group_data.get("customer_group_name") or str(erpnext_id or ""),
                    parent_customer_group=group_data.get("parent_customer_group"),
                    is_group=group_data.get("is_group", 0) == 1,
                    default_price_list=group_data.get("default_price_list"),
                    default_payment_terms_template=group_data.get("default_payment_terms_template"),
                    lft=group_data.get("lft"),
                    rgt=group_data.get("rgt"),
                )
                sync_client.db.add(customer_group)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_territories(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync territories from ERPNext."""
    sync_client.start_sync("territories", "full" if full_sync else "incremental")

    try:
        territories = await sync_client._fetch_all_doctype(
            client,
            "Territory",
            fields=["*"],
        )

        for terr_data in territories:
            erpnext_id = terr_data.get("name")
            existing = sync_client.db.query(Territory).filter(
                Territory.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.territory_name = terr_data.get("territory_name") or str(erpnext_id or "")
                existing.parent_territory = terr_data.get("parent_territory")
                existing.is_group = terr_data.get("is_group", 0) == 1
                existing.territory_manager = terr_data.get("territory_manager")
                existing.lft = terr_data.get("lft")
                existing.rgt = terr_data.get("rgt")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                territory = Territory(
                    erpnext_id=erpnext_id,
                    territory_name=terr_data.get("territory_name") or str(erpnext_id or ""),
                    parent_territory=terr_data.get("parent_territory"),
                    is_group=terr_data.get("is_group", 0) == 1,
                    territory_manager=terr_data.get("territory_manager"),
                    lft=terr_data.get("lft"),
                    rgt=terr_data.get("rgt"),
                )
                sync_client.db.add(territory)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_sales_persons(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync sales persons from ERPNext."""
    sync_client.start_sync("sales_persons", "full" if full_sync else "incremental")

    try:
        persons = await sync_client._fetch_all_doctype(
            client,
            "Sales Person",
            fields=["*"],
        )

        for person_data in persons:
            erpnext_id = person_data.get("name")
            existing = sync_client.db.query(SalesPerson).filter(
                SalesPerson.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.sales_person_name = person_data.get("sales_person_name") or str(erpnext_id or "")
                existing.parent_sales_person = person_data.get("parent_sales_person")
                existing.is_group = person_data.get("is_group", 0) == 1
                existing.employee = person_data.get("employee")
                existing.department = person_data.get("department")
                existing.enabled = person_data.get("enabled", 1) == 1
                existing.commission_rate = Decimal(str(person_data.get("commission_rate", 0) or 0))
                existing.lft = person_data.get("lft")
                existing.rgt = person_data.get("rgt")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                sales_person = SalesPerson(
                    erpnext_id=erpnext_id,
                    sales_person_name=person_data.get("sales_person_name") or str(erpnext_id or ""),
                    parent_sales_person=person_data.get("parent_sales_person"),
                    is_group=person_data.get("is_group", 0) == 1,
                    employee=person_data.get("employee"),
                    department=person_data.get("department"),
                    enabled=person_data.get("enabled", 1) == 1,
                    commission_rate=Decimal(str(person_data.get("commission_rate", 0) or 0)),
                    lft=person_data.get("lft"),
                    rgt=person_data.get("rgt"),
                )
                sync_client.db.add(sales_person)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_erpnext_leads(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync leads from ERPNext CRM."""
    sync_client.start_sync("erpnext_leads", "full" if full_sync else "incremental")

    try:
        leads = await sync_client._fetch_all_doctype(
            client,
            "Lead",
            fields=["*"],
        )

        batch_size = 500
        for i, lead_data in enumerate(leads, 1):
            erpnext_id = lead_data.get("name")
            existing = sync_client.db.query(ERPNextLead).filter(
                ERPNextLead.erpnext_id == erpnext_id
            ).first()

            # Map status
            status_str = (lead_data.get("status", "") or "").lower().replace(" ", "_")
            status_map = {
                "lead": ERPNextLeadStatus.LEAD,
                "open": ERPNextLeadStatus.OPEN,
                "replied": ERPNextLeadStatus.REPLIED,
                "opportunity": ERPNextLeadStatus.OPPORTUNITY,
                "quotation": ERPNextLeadStatus.QUOTATION,
                "lost_quotation": ERPNextLeadStatus.LOST_QUOTATION,
                "interested": ERPNextLeadStatus.INTERESTED,
                "converted": ERPNextLeadStatus.CONVERTED,
                "do_not_contact": ERPNextLeadStatus.DO_NOT_CONTACT,
            }
            status = status_map.get(status_str, ERPNextLeadStatus.LEAD)

            if existing:
                existing.lead_name = lead_data.get("lead_name", "")
                existing.company_name = lead_data.get("company_name")
                existing.email_id = lead_data.get("email_id")
                existing.phone = lead_data.get("phone")
                existing.mobile_no = lead_data.get("mobile_no")
                existing.website = lead_data.get("website")
                existing.source = lead_data.get("source")
                existing.lead_owner = lead_data.get("lead_owner")
                existing.territory = lead_data.get("territory")
                existing.industry = lead_data.get("industry")
                existing.market_segment = lead_data.get("market_segment")
                existing.status = status
                existing.qualification_status = lead_data.get("qualification_status")
                existing.city = lead_data.get("city")
                existing.state = lead_data.get("state")
                existing.country = lead_data.get("country")
                existing.notes = lead_data.get("notes")
                existing.converted = lead_data.get("converted", 0) == 1 or status == ERPNextLeadStatus.CONVERTED
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                lead = ERPNextLead(
                    erpnext_id=erpnext_id,
                    lead_name=lead_data.get("lead_name", ""),
                    company_name=lead_data.get("company_name"),
                    email_id=lead_data.get("email_id"),
                    phone=lead_data.get("phone"),
                    mobile_no=lead_data.get("mobile_no"),
                    website=lead_data.get("website"),
                    source=lead_data.get("source"),
                    lead_owner=lead_data.get("lead_owner"),
                    territory=lead_data.get("territory"),
                    industry=lead_data.get("industry"),
                    market_segment=lead_data.get("market_segment"),
                    status=status,
                    qualification_status=lead_data.get("qualification_status"),
                    city=lead_data.get("city"),
                    state=lead_data.get("state"),
                    country=lead_data.get("country"),
                    notes=lead_data.get("notes"),
                    converted=lead_data.get("converted", 0) == 1 or status == ERPNextLeadStatus.CONVERTED,
                )
                sync_client.db.add(lead)
                sync_client.increment_created()

            # Batch commit
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("erpnext_leads_batch_committed", processed=i, total=len(leads))

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_quotations(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync quotations from ERPNext."""
    sync_client.start_sync("quotations", "full" if full_sync else "incremental")

    try:
        quotations = await sync_client._fetch_all_doctype(
            client,
            "Quotation",
            fields=["*"],
        )

        batch_size = 500
        for i, quote_data in enumerate(quotations, 1):
            erpnext_id = quote_data.get("name")
            existing = sync_client.db.query(Quotation).filter(
                Quotation.erpnext_id == erpnext_id
            ).first()

            # Map status
            status_str = (quote_data.get("status", "") or "").lower()
            status_map = {
                "draft": QuotationStatus.DRAFT,
                "open": QuotationStatus.OPEN,
                "replied": QuotationStatus.REPLIED,
                "ordered": QuotationStatus.ORDERED,
                "lost": QuotationStatus.LOST,
                "cancelled": QuotationStatus.CANCELLED,
                "expired": QuotationStatus.EXPIRED,
            }
            status = status_map.get(status_str, QuotationStatus.DRAFT)

            if existing:
                existing.quotation_to = quote_data.get("quotation_to")
                existing.party_name = quote_data.get("party_name")
                existing.customer_name = quote_data.get("customer_name")
                existing.order_type = quote_data.get("order_type")
                existing.company = quote_data.get("company")
                existing.currency = quote_data.get("currency", "NGN")
                existing.total_qty = Decimal(str(quote_data.get("total_qty", 0) or 0))
                existing.total = Decimal(str(quote_data.get("total", 0) or 0))
                existing.net_total = Decimal(str(quote_data.get("net_total", 0) or 0))
                existing.grand_total = Decimal(str(quote_data.get("grand_total", 0) or 0))
                existing.rounded_total = Decimal(str(quote_data.get("rounded_total", 0) or 0))
                existing.total_taxes_and_charges = Decimal(str(quote_data.get("total_taxes_and_charges", 0) or 0))
                existing.status = status
                existing.docstatus = quote_data.get("docstatus", 0)
                existing.sales_partner = quote_data.get("sales_partner")
                existing.territory = quote_data.get("territory")
                existing.source = quote_data.get("source")
                existing.campaign = quote_data.get("campaign")
                existing.order_lost_reason = quote_data.get("order_lost_reason")
                existing.last_synced_at = datetime.utcnow()

                if quote_data.get("transaction_date"):
                    try:
                        existing.transaction_date = datetime.fromisoformat(quote_data["transaction_date"]).date()
                    except (ValueError, TypeError):
                        pass

                if quote_data.get("valid_till"):
                    try:
                        existing.valid_till = datetime.fromisoformat(quote_data["valid_till"]).date()
                    except (ValueError, TypeError):
                        pass

                sync_client.increment_updated()
            else:
                quotation = Quotation(
                    erpnext_id=erpnext_id,
                    quotation_to=quote_data.get("quotation_to"),
                    party_name=quote_data.get("party_name"),
                    customer_name=quote_data.get("customer_name"),
                    order_type=quote_data.get("order_type"),
                    company=quote_data.get("company"),
                    currency=quote_data.get("currency", "NGN"),
                    total_qty=Decimal(str(quote_data.get("total_qty", 0) or 0)),
                    total=Decimal(str(quote_data.get("total", 0) or 0)),
                    net_total=Decimal(str(quote_data.get("net_total", 0) or 0)),
                    grand_total=Decimal(str(quote_data.get("grand_total", 0) or 0)),
                    rounded_total=Decimal(str(quote_data.get("rounded_total", 0) or 0)),
                    total_taxes_and_charges=Decimal(str(quote_data.get("total_taxes_and_charges", 0) or 0)),
                    status=status,
                    docstatus=quote_data.get("docstatus", 0),
                    sales_partner=quote_data.get("sales_partner"),
                    territory=quote_data.get("territory"),
                    source=quote_data.get("source"),
                    campaign=quote_data.get("campaign"),
                    order_lost_reason=quote_data.get("order_lost_reason"),
                )

                if quote_data.get("transaction_date"):
                    try:
                        quotation.transaction_date = datetime.fromisoformat(quote_data["transaction_date"]).date()
                    except (ValueError, TypeError):
                        pass

                if quote_data.get("valid_till"):
                    try:
                        quotation.valid_till = datetime.fromisoformat(quote_data["valid_till"]).date()
                    except (ValueError, TypeError):
                        pass

                sync_client.db.add(quotation)
                sync_client.increment_created()

            # Batch commit
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("quotations_batch_committed", processed=i, total=len(quotations))

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_sales_orders(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync sales orders from ERPNext."""
    sync_client.start_sync("sales_orders", "full" if full_sync else "incremental")

    try:
        orders = await sync_client._fetch_all_doctype(
            client,
            "Sales Order",
            fields=["*"],
        )

        # Pre-fetch customers by erpnext_id for FK linking
        customers_by_erpnext_id = {
            c.erpnext_id: c.id
            for c in sync_client.db.query(Customer).filter(Customer.erpnext_id.isnot(None)).all()
        }

        batch_size = 500
        for i, order_data in enumerate(orders, 1):
            erpnext_id = order_data.get("name")
            existing = sync_client.db.query(SalesOrder).filter(
                SalesOrder.erpnext_id == erpnext_id
            ).first()

            # Map status
            status_str = (order_data.get("status", "") or "").lower().replace(" ", "_")
            status_map = {
                "draft": SalesOrderStatus.DRAFT,
                "to_deliver_and_bill": SalesOrderStatus.TO_DELIVER_AND_BILL,
                "to_bill": SalesOrderStatus.TO_BILL,
                "to_deliver": SalesOrderStatus.TO_DELIVER,
                "completed": SalesOrderStatus.COMPLETED,
                "cancelled": SalesOrderStatus.CANCELLED,
                "closed": SalesOrderStatus.CLOSED,
                "on_hold": SalesOrderStatus.ON_HOLD,
            }
            status = status_map.get(status_str, SalesOrderStatus.DRAFT)

            # Link to customer
            erpnext_customer = order_data.get("customer")
            customer_id = customers_by_erpnext_id.get(erpnext_customer) if erpnext_customer else None

            if existing:
                existing.customer = erpnext_customer
                existing.customer_name = order_data.get("customer_name")
                existing.customer_id = customer_id
                existing.order_type = order_data.get("order_type")
                existing.company = order_data.get("company")
                existing.currency = order_data.get("currency", "NGN")
                existing.total_qty = Decimal(str(order_data.get("total_qty", 0) or 0))
                existing.total = Decimal(str(order_data.get("total", 0) or 0))
                existing.net_total = Decimal(str(order_data.get("net_total", 0) or 0))
                existing.grand_total = Decimal(str(order_data.get("grand_total", 0) or 0))
                existing.rounded_total = Decimal(str(order_data.get("rounded_total", 0) or 0))
                existing.total_taxes_and_charges = Decimal(str(order_data.get("total_taxes_and_charges", 0) or 0))
                existing.per_delivered = Decimal(str(order_data.get("per_delivered", 0) or 0))
                existing.per_billed = Decimal(str(order_data.get("per_billed", 0) or 0))
                existing.billing_status = order_data.get("billing_status")
                existing.delivery_status = order_data.get("delivery_status")
                existing.status = status
                existing.docstatus = order_data.get("docstatus", 0)
                existing.sales_partner = order_data.get("sales_partner")
                existing.territory = order_data.get("territory")
                existing.source = order_data.get("source")
                existing.campaign = order_data.get("campaign")
                existing.last_synced_at = datetime.utcnow()

                if order_data.get("transaction_date"):
                    try:
                        existing.transaction_date = datetime.fromisoformat(order_data["transaction_date"]).date()
                    except (ValueError, TypeError):
                        pass

                if order_data.get("delivery_date"):
                    try:
                        existing.delivery_date = datetime.fromisoformat(order_data["delivery_date"]).date()
                    except (ValueError, TypeError):
                        pass

                sync_client.increment_updated()
            else:
                sales_order = SalesOrder(
                    erpnext_id=erpnext_id,
                    customer=erpnext_customer,
                    customer_name=order_data.get("customer_name"),
                    customer_id=customer_id,
                    order_type=order_data.get("order_type"),
                    company=order_data.get("company"),
                    currency=order_data.get("currency", "NGN"),
                    total_qty=Decimal(str(order_data.get("total_qty", 0) or 0)),
                    total=Decimal(str(order_data.get("total", 0) or 0)),
                    net_total=Decimal(str(order_data.get("net_total", 0) or 0)),
                    grand_total=Decimal(str(order_data.get("grand_total", 0) or 0)),
                    rounded_total=Decimal(str(order_data.get("rounded_total", 0) or 0)),
                    total_taxes_and_charges=Decimal(str(order_data.get("total_taxes_and_charges", 0) or 0)),
                    per_delivered=Decimal(str(order_data.get("per_delivered", 0) or 0)),
                    per_billed=Decimal(str(order_data.get("per_billed", 0) or 0)),
                    billing_status=order_data.get("billing_status"),
                    delivery_status=order_data.get("delivery_status"),
                    status=status,
                    docstatus=order_data.get("docstatus", 0),
                    sales_partner=order_data.get("sales_partner"),
                    territory=order_data.get("territory"),
                    source=order_data.get("source"),
                    campaign=order_data.get("campaign"),
                )

                if order_data.get("transaction_date"):
                    try:
                        sales_order.transaction_date = datetime.fromisoformat(order_data["transaction_date"]).date()
                    except (ValueError, TypeError):
                        pass

                if order_data.get("delivery_date"):
                    try:
                        sales_order.delivery_date = datetime.fromisoformat(order_data["delivery_date"]).date()
                    except (ValueError, TypeError):
                        pass

                sync_client.db.add(sales_order)
                sync_client.increment_created()

            # Batch commit
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("sales_orders_batch_committed", processed=i, total=len(orders))

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
