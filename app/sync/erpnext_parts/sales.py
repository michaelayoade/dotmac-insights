"""Sales sync functions for ERPNext.

This module handles syncing of sales-related entities:
- Customers, Customer Groups
- Territories, Sales Persons
- Leads, Quotations, Sales Orders
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
import structlog

from app.models.party import (
    CustomerAccount,
    Party,
    PartyExternalId,
    PartyRole,
    PartyType,
)
from app.models.employee import Employee
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

        # Pre-fetch party external IDs for erpnext/splynx lookups
        party_ext_ids = (
            sync_client.db.query(PartyExternalId)
            .filter(PartyExternalId.system.in_(["erpnext", "splynx"]))
            .all()
        )
        party_by_ext = {(p.system, p.external_id): p.party_id for p in party_ext_ids}

        party_email_index = {
            (p.primary_email or "").lower(): p
            for p in sync_client.db.query(Party).filter(Party.primary_email.isnot(None)).all()
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

            # Ensure party-based identity records exist
            party = None
            created = False
            if erpnext_id:
                party_id = party_by_ext.get(("erpnext", str(erpnext_id)))
                if party_id:
                    party = sync_client.db.query(Party).get(party_id)

            if not party and splynx_id is not None:
                party_id = party_by_ext.get(("splynx", str(splynx_id)))
                if party_id:
                    party = sync_client.db.query(Party).get(party_id)

            if not party:
                email = (cust_data.get("email_id") or "").strip().lower()
                if email:
                    party = party_email_index.get(email)

            if not party:
                customer_type = (cust_data.get("customer_type") or "").strip().lower()
                party_type = PartyType.ORGANIZATION.value if customer_type == "company" else PartyType.PERSON.value
                party = Party(
                    type=party_type,
                    name=cust_data.get("customer_name", "") or None,
                    emails=[],
                    phones=[],
                )
                sync_client.db.add(party)
                sync_client.db.flush()
                created = True

            email = cust_data.get("email_id")
            if email:
                email_norm = email.strip().lower()
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
                    party_email_index[email_norm] = party

            phone = cust_data.get("mobile_no") or cust_data.get("custom_phone_numbers")
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

            if not party.name:
                party.name = cust_data.get("customer_name") or party.name

            # External ID mappings for party
            if erpnext_id and ("erpnext", str(erpnext_id)) not in party_by_ext:
                sync_client.db.add(
                    PartyExternalId(
                        party_id=party.id,
                        system="erpnext",
                        external_id=str(erpnext_id),
                        external_key_type="customer_id",
                    )
                )
                party_by_ext[("erpnext", str(erpnext_id))] = party.id

            if splynx_id is not None and ("splynx", str(splynx_id)) not in party_by_ext:
                sync_client.db.add(
                    PartyExternalId(
                        party_id=party.id,
                        system="splynx",
                        external_id=str(splynx_id),
                        external_key_type="customer_id",
                    )
                )
                party_by_ext[("splynx", str(splynx_id))] = party.id

            # Ensure customer role exists
            has_customer_role = (
                sync_client.db.query(PartyRole)
                .filter(PartyRole.party_id == party.id, PartyRole.role == "customer", PartyRole.until.is_(None))
                .first()
            )
            if not has_customer_role:
                sync_client.db.add(PartyRole(party_id=party.id, role="customer"))

            # Ensure customer account exists
            account = (
                sync_client.db.query(CustomerAccount)
                .filter(CustomerAccount.party_id == party.id)
                .first()
            )
            if not account:
                status = "suspended" if cust_data.get("disabled") else "active"
                account = CustomerAccount(
                    party_id=party.id,
                    account_number=str(erpnext_id or party.id),
                    status=status,
                    external_ids={
                        "erpnext_id": erpnext_id,
                        "splynx_id": splynx_id,
                    },
                    billing_email=cust_data.get("email_id"),
                )
                sync_client.db.add(account)
                created = True
            else:
                if cust_data.get("disabled"):
                    account.status = "suspended"
                if not account.billing_email:
                    account.billing_email = cust_data.get("email_id")

            custom_fields = dict(party.custom_fields or {})
            custom_fields.update(
                {
                    "erpnext_customer_type": cust_data.get("customer_type"),
                    "custom_gps": cust_data.get("custom_gps"),
                    "custom_city": cust_data.get("custom_city"),
                    "custom_region": cust_data.get("custom_region"),
                    "custom_building_type": cust_data.get("custom_building_type"),
                    "custom_notes": cust_data.get("custom_notes"),
                }
            )
            party.custom_fields = custom_fields

            if cust_data.get("customer_name") and not party.name:
                party.name = cust_data.get("customer_name")

            account.external_ids = {
                **(account.external_ids or {}),
                "erpnext_id": erpnext_id,
                "splynx_id": splynx_id,
            }

            if created:
                sync_client.increment_created()
            else:
                sync_client.increment_updated()

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
                existing.last_synced_at = datetime.now(timezone.utc)
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
                existing.last_synced_at = datetime.now(timezone.utc)
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
        employees_by_erpnext_id = {
            e.erpnext_id: e
            for e in sync_client.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).all()
        }

        for person_data in persons:
            erpnext_id = person_data.get("name")
            employee_erpnext_id = person_data.get("employee")
            employee = employees_by_erpnext_id.get(employee_erpnext_id)
            existing = sync_client.db.query(SalesPerson).filter(
                SalesPerson.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.sales_person_name = person_data.get("sales_person_name") or str(erpnext_id or "")
                existing.parent_sales_person = person_data.get("parent_sales_person")
                existing.is_group = person_data.get("is_group", 0) == 1
                existing.employee = person_data.get("employee")
                existing.department = person_data.get("department")
                existing.employee_id = employee.id if employee else None
                existing.party_id = employee.party_id if employee else None
                existing.enabled = person_data.get("enabled", 1) == 1
                existing.commission_rate = Decimal(str(person_data.get("commission_rate", 0) or 0))
                existing.lft = person_data.get("lft")
                existing.rgt = person_data.get("rgt")
                existing.last_synced_at = datetime.now(timezone.utc)
                sync_client.increment_updated()
            else:
                sales_person = SalesPerson(
                    erpnext_id=erpnext_id,
                    sales_person_name=person_data.get("sales_person_name") or str(erpnext_id or ""),
                    parent_sales_person=person_data.get("parent_sales_person"),
                    is_group=person_data.get("is_group", 0) == 1,
                    employee=person_data.get("employee"),
                    department=person_data.get("department"),
                    employee_id=employee.id if employee else None,
                    party_id=employee.party_id if employee else None,
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

        party_exts = (
            sync_client.db.query(PartyExternalId)
            .filter(
                PartyExternalId.system == "erpnext",
                PartyExternalId.external_key_type == "lead_id",
            )
            .all()
        )
        party_by_ext = {p.external_id: p.party_id for p in party_exts}
        party_email_index = {
            (p.primary_email or "").lower(): p
            for p in sync_client.db.query(Party).filter(Party.primary_email.isnot(None)).all()
        }

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

            # Link or create party for this lead
            party = None
            if existing and existing.party_id:
                party = sync_client.db.query(Party).get(existing.party_id)

            if not party and erpnext_id:
                party_id = party_by_ext.get(str(erpnext_id))
                if party_id:
                    party = sync_client.db.query(Party).get(party_id)

            email = (lead_data.get("email_id") or "").strip().lower()
            if not party and email:
                party = party_email_index.get(email)

            if not party:
                company_name = lead_data.get("company_name") or None
                party_type = PartyType.ORGANIZATION.value if company_name else PartyType.PERSON.value
                party = Party(
                    type=party_type,
                    name=company_name or lead_data.get("lead_name") or None,
                    emails=[],
                    phones=[],
                )
                sync_client.db.add(party)
                sync_client.db.flush()

            if email:
                emails = list(party.emails or [])
                if not any((e.get("address") or "").lower() == email for e in emails):
                    emails.append(
                        {
                            "address": email,
                            "label": "primary",
                            "is_primary": len(emails) == 0,
                            "verified": False,
                        }
                    )
                    party.emails = emails
                    party_email_index[email] = party

            phone = lead_data.get("phone") or lead_data.get("mobile_no")
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

            if not party.name:
                party.name = lead_data.get("company_name") or lead_data.get("lead_name") or party.name

            if erpnext_id and str(erpnext_id) not in party_by_ext:
                sync_client.db.add(
                    PartyExternalId(
                        party_id=party.id,
                        system="erpnext",
                        external_id=str(erpnext_id),
                        external_key_type="lead_id",
                    )
                )
                party_by_ext[str(erpnext_id)] = party.id

            has_lead_role = (
                sync_client.db.query(PartyRole)
                .filter(PartyRole.party_id == party.id, PartyRole.role == "lead", PartyRole.until.is_(None))
                .first()
            )
            if not has_lead_role:
                sync_client.db.add(PartyRole(party_id=party.id, role="lead"))

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
                existing.party_id = party.id
                existing.last_synced_at = datetime.now(timezone.utc)
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
                    party_id=party.id,
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
                existing.last_synced_at = datetime.now(timezone.utc)

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

        # Pre-fetch customer accounts by erpnext_id for FK linking
        accounts_by_erpnext_id = {
            pe.external_id: (ca.id, ca.party_id)
            for pe, ca in (
                sync_client.db.query(PartyExternalId, CustomerAccount)
                .join(CustomerAccount, CustomerAccount.party_id == PartyExternalId.party_id)
                .filter(
                    PartyExternalId.system == "erpnext",
                    PartyExternalId.external_key_type == "customer_id",
                )
                .all()
            )
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

            # Link to customer account
            erpnext_customer = order_data.get("customer")
            customer_account_id = None
            party_id = None
            if erpnext_customer:
                account_tuple = accounts_by_erpnext_id.get(str(erpnext_customer))
                if account_tuple:
                    customer_account_id, party_id = account_tuple

            if existing:
                existing.customer = erpnext_customer
                existing.customer_name = order_data.get("customer_name")
                existing.customer_account_id = customer_account_id
                existing.party_id = party_id
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
                existing.last_synced_at = datetime.now(timezone.utc)

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
                    customer_account_id=customer_account_id,
                    party_id=party_id,
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
