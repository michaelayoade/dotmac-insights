from __future__ import annotations

import httpx
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
import structlog
from sqlalchemy.orm import Session
from sqlalchemy import func
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.sync.base import BaseSyncClient
from app.models.sync_log import SyncSource
from app.models.customer import Customer
from app.models.employee import Employee, EmploymentStatus
from app.models.expense import Expense, ExpenseStatus
from app.models.invoice import Invoice, InvoiceStatus, InvoiceSource
from app.models.payment import Payment, PaymentMethod, PaymentSource, PaymentStatus
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketSource
from app.models.project import Project, ProjectStatus, ProjectPriority
from app.models.accounting import (
    BankAccount,
    JournalEntry,
    JournalEntryType,
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    GLEntry,
    Account,
    AccountType,
    BankTransaction,
    BankTransactionStatus,
    Supplier,
    ModeOfPayment,
    PaymentModeType,
    CostCenter,
    FiscalYear,
)
from app.models.sales import (
    SalesOrder,
    SalesOrderStatus,
    Quotation,
    QuotationStatus,
    ERPNextLead,
    ERPNextLeadStatus,
    Item,
    CustomerGroup,
    Territory,
    SalesPerson,
    ItemGroup,
)
from app.models.hr import (
    Department,
    HDTeam,
    HDTeamMember,
    Designation,
    ERPNextUser,
)

logger = structlog.get_logger()


class ERPNextSync(BaseSyncClient):
    """Sync client for ERPNext ERP system."""

    source = SyncSource.ERPNEXT

    def __init__(self, db: Session):
        super().__init__(db)
        self.base_url = settings.erpnext_api_url.rstrip("/")
        self.api_key = settings.erpnext_api_key
        self.api_secret = settings.erpnext_api_secret

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        """Parse an integer from ERPNext custom fields if present."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_iso_date(value: Any) -> Optional[datetime]:
        """Best-effort ISO date parser used for ERPNext date fields."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None

    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers for ERPNext API."""
        return {
            "Authorization": f"token {self.api_key}:{self.api_secret}",
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make authenticated request to ERPNext API."""
        response = await client.request(
            method,
            f"{self.base_url}{endpoint}",
            headers=self._get_headers(),
            params=params,
            json=json,
        )
        response.raise_for_status()
        return response.json()

    async def _fetch_doctype(
        self,
        client: httpx.AsyncClient,
        doctype: str,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit_start: int = 0,
        limit_page_length: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch records of a specific doctype."""
        import json

        params: Dict[str, Any] = {
            "limit_start": limit_start,
            "limit_page_length": limit_page_length,
        }

        if fields:
            # ERPNext requires JSON array with double quotes
            params["fields"] = json.dumps(fields)

        if filters:
            params["filters"] = json.dumps(filters)

        data = await self._request(client, "GET", "/api/resource/" + doctype, params=params)
        result: List[Dict[str, Any]] = data.get("data", [])
        return result

    async def _fetch_all_doctype(
        self,
        client: httpx.AsyncClient,
        doctype: str,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all records with pagination."""
        all_records = []
        limit_start = 0
        limit_page_length = 100

        while True:
            records = await self._fetch_doctype(
                client,
                doctype,
                fields=fields,
                filters=filters,
                limit_start=limit_start,
                limit_page_length=limit_page_length,
            )

            if not records:
                break

            all_records.extend(records)
            self.increment_fetched(len(records))

            if len(records) < limit_page_length:
                break

            limit_start += limit_page_length

        return all_records

    async def _fetch_document(
        self,
        client: httpx.AsyncClient,
        doctype: str,
        name: str,
    ) -> Dict[str, Any]:
        """Fetch a single document by name, including child tables."""
        from urllib.parse import quote

        # URL encode the document name to handle special characters
        encoded_name = quote(name, safe="")
        data = await self._request(client, "GET", f"/api/resource/{doctype}/{encoded_name}")
        result: Dict[str, Any] = data.get("data", {})
        return result

    async def test_connection(self) -> bool:
        """Test if ERPNext API connection is working."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await self._fetch_doctype(client, "Company", limit_page_length=1)
            return True
        except Exception as e:
            logger.error("erpnext_connection_test_failed", error=str(e))
            return False

    async def sync_all(self, full_sync: bool = False):
        """Sync all entities from ERPNext."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_customers(client, full_sync)
            await self.sync_employees(client, full_sync)
            await self.sync_invoices(client, full_sync)
            await self.sync_payments(client, full_sync)
            await self.sync_expenses(client, full_sync)
            await self.sync_hd_tickets(client, full_sync)
            await self.sync_projects(client, full_sync)

    # Task wrapper methods for Celery (creates own httpx client)
    async def sync_hd_tickets_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs HD Tickets with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_hd_tickets(client, full_sync)

    async def sync_customers(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync customers from ERPNext (to match with Splynx customers).

        Uses custom_splynx_id for primary matching, then email, then creates new.
        """
        self.start_sync("customers", "full" if full_sync else "incremental")

        try:
            # Fetch all fields including custom fields
            customers = await self._fetch_all_doctype(
                client,
                "Customer",
                fields=["*"],  # Get all fields including custom_splynx_id
            )

            # Pre-fetch existing customers by splynx_id for efficient matching
            customers_by_splynx_id = {
                c.splynx_id: c
                for c in self.db.query(Customer).filter(Customer.splynx_id.isnot(None)).all()
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
                existing = self.db.query(Customer).filter(
                    Customer.erpnext_id == erpnext_id
                ).first()

                # Priority 2: Match by splynx_id from ERPNext custom field
                if not existing and splynx_id:
                    existing = customers_by_splynx_id.get(splynx_id)

                # Priority 3: Match by email
                if not existing:
                    email = cust_data.get("email_id")
                    if email:
                        existing = self.db.query(Customer).filter(
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
                    self.increment_updated()
                else:
                    # Create new customer record with all available data
                    customer = Customer(
                        erpnext_id=erpnext_id,
                        splynx_id=splynx_id,  # Link via custom_splynx_id
                        name=cust_data.get("customer_name", ""),
                        email=cust_data.get("email_id"),
                        phone=cust_data.get("mobile_no") or cust_data.get("custom_phone_numbers"),
                        gps=cust_data.get("custom_gps"),
                        city=cust_data.get("custom_city"),
                        state=cust_data.get("custom_region"),
                        building_type=cust_data.get("custom_building_type"),
                        notes=cust_data.get("custom_notes"),
                    )
                    self.db.add(customer)
                    self.increment_created()

                # Batch commit
                if i % batch_size == 0:
                    self.db.commit()
                    logger.debug("erpnext_customers_batch_committed", processed=i, total=len(customers))

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_employees(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync employees from ERPNext."""
        self.start_sync("employees", "full" if full_sync else "incremental")

        try:
            employees = await self._fetch_all_doctype(
                client,
                "Employee",
                fields=[
                    "name", "employee_name", "company_email", "cell_number",
                    "designation", "department", "reports_to", "status",
                    "employment_type", "date_of_joining", "relieving_date",
                ],
            )

            for emp_data in employees:
                erpnext_id = emp_data.get("name")
                existing = self.db.query(Employee).filter(Employee.erpnext_id == erpnext_id).first()

                # Map status
                status_str = (emp_data.get("status", "") or "").lower()
                status_map = {
                    "active": EmploymentStatus.ACTIVE,
                    "inactive": EmploymentStatus.INACTIVE,
                    "left": EmploymentStatus.TERMINATED,
                    "on_leave": EmploymentStatus.ON_LEAVE,
                }
                status = status_map.get(status_str, EmploymentStatus.ACTIVE)

                if existing:
                    existing.name = emp_data.get("employee_name", "")
                    existing.email = emp_data.get("company_email")
                    existing.phone = emp_data.get("cell_number")
                    existing.designation = emp_data.get("designation")
                    existing.department = emp_data.get("department")
                    existing.reports_to = emp_data.get("reports_to")
                    existing.status = status
                    existing.employment_type = emp_data.get("employment_type")
                    existing.last_synced_at = datetime.utcnow()

                    if emp_data.get("date_of_joining"):
                        try:
                            existing.date_of_joining = datetime.fromisoformat(emp_data["date_of_joining"])
                        except (ValueError, TypeError):
                            pass

                    if emp_data.get("relieving_date"):
                        try:
                            existing.date_of_leaving = datetime.fromisoformat(emp_data["relieving_date"])
                        except (ValueError, TypeError):
                            pass

                    self.increment_updated()
                else:
                    employee = Employee(
                        erpnext_id=erpnext_id,
                        employee_number=emp_data.get("name"),
                        name=emp_data.get("employee_name", ""),
                        email=emp_data.get("company_email"),
                        phone=emp_data.get("cell_number"),
                        designation=emp_data.get("designation"),
                        department=emp_data.get("department"),
                        reports_to=emp_data.get("reports_to"),
                        status=status,
                        employment_type=emp_data.get("employment_type"),
                    )

                    if emp_data.get("date_of_joining"):
                        try:
                            employee.date_of_joining = datetime.fromisoformat(emp_data["date_of_joining"])
                        except (ValueError, TypeError):
                            pass

                    self.db.add(employee)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_invoices(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync sales invoices from ERPNext."""
        self.start_sync("invoices", "full" if full_sync else "incremental")

        try:
            invoices = await self._fetch_all_doctype(
                client,
                "Sales Invoice",
                fields=[
                "name", "customer", "posting_date", "due_date",
                "grand_total", "outstanding_amount", "status",
                "paid_amount", "currency",
                "custom_splynx_invoice_id",
            ],
            )

            # Track invoice IDs already assigned an erpnext_id in this transaction
            assigned_invoice_ids: set[int] = set()
            # Track erpnext_ids already processed in this transaction
            processed_erpnext_ids: set[str] = set()

            for inv_data in invoices:
                erpnext_id = inv_data.get("name")

                # Skip if this erpnext_id was already processed in this batch
                if erpnext_id in processed_erpnext_ids:
                    continue
                processed_erpnext_ids.add(erpnext_id)
                custom_splynx_invoice_id = self._safe_int(inv_data.get("custom_splynx_invoice_id"))
                splynx_invoice = (
                    self.db.query(Invoice)
                    .filter(Invoice.splynx_id == custom_splynx_invoice_id)
                    .first()
                    if custom_splynx_invoice_id
                    else None
                )

                existing_erpnext = self.db.query(Invoice).filter(
                    Invoice.erpnext_id == erpnext_id
                ).first()

                # Find customer
                customer_erpnext_id = inv_data.get("customer")
                customer = self.db.query(Customer).filter(
                    Customer.erpnext_id == customer_erpnext_id
                ).first()
                customer_id = customer.id if customer else None

                # Map status
                status_str = (inv_data.get("status", "") or "").lower()
                status_map = {
                    "paid": InvoiceStatus.PAID,
                    "unpaid": InvoiceStatus.PENDING,
                    "overdue": InvoiceStatus.OVERDUE,
                    "partly paid": InvoiceStatus.PARTIALLY_PAID,
                    "cancelled": InvoiceStatus.CANCELLED,
                    "return": InvoiceStatus.REFUNDED,
                }
                status = status_map.get(status_str, InvoiceStatus.PENDING)

                total_amount = float(inv_data.get("grand_total", 0) or 0)
                outstanding = float(inv_data.get("outstanding_amount", 0) or 0)
                paid_amount = float(inv_data.get("paid_amount", 0) or 0)

                # Determine target invoice, handling conflicts between splynx linkage and existing erpnext record
                target_invoice: Optional[Invoice] = None
                duplicate_invoice: Optional[Invoice] = None

                if splynx_invoice and existing_erpnext:
                    if splynx_invoice.id == existing_erpnext.id:
                        # Same invoice - use it
                        target_invoice = splynx_invoice
                    elif existing_erpnext.source == InvoiceSource.ERPNEXT:
                        # Existing ERPNext-only record can be merged into Splynx record
                        target_invoice = splynx_invoice
                        duplicate_invoice = existing_erpnext
                    else:
                        # Conflict: existing_erpnext is a Splynx invoice with this erpnext_id
                        # This is a data integrity issue - use existing_erpnext to avoid unique constraint violation
                        # Log warning and skip updating the linkage
                        import structlog
                        logger = structlog.get_logger()
                        logger.warning(
                            "erpnext_splynx_linkage_conflict",
                            erpnext_id=erpnext_id,
                            custom_splynx_id=custom_splynx_invoice_id,
                            existing_invoice_id=existing_erpnext.id,
                            linked_splynx_invoice_id=splynx_invoice.id,
                        )
                        target_invoice = existing_erpnext
                elif splynx_invoice:
                    target_invoice = splynx_invoice
                elif existing_erpnext:
                    target_invoice = existing_erpnext

                # Fallback soft match if the custom field is missing
                if not target_invoice:
                    posting_dt = self._parse_iso_date(inv_data.get("posting_date"))
                    if posting_dt and customer_id:
                        # Exclude invoices already assigned in this transaction or already having an erpnext_id
                        target_invoice = (
                            self.db.query(Invoice)
                            .filter(
                                Invoice.source == InvoiceSource.SPLYNX,
                                Invoice.customer_id == customer_id,
                                Invoice.total_amount == Decimal(str(total_amount)),
                                func.date(Invoice.invoice_date) == posting_dt.date(),
                                Invoice.erpnext_id.is_(None),
                                ~Invoice.id.in_(assigned_invoice_ids) if assigned_invoice_ids else True,
                            )
                            .first()
                        )

                if target_invoice:
                    # Track this invoice as assigned to avoid duplicate erpnext_id assignments
                    assigned_invoice_ids.add(target_invoice.id)

                    # If we're merging with a duplicate, clear its erpnext_id first to avoid constraint violation
                    if duplicate_invoice:
                        duplicate_invoice.erpnext_id = None
                        self.db.flush()  # Flush the NULL assignment before setting the new value

                    target_invoice.erpnext_id = erpnext_id
                    target_invoice.customer_id = customer_id
                    target_invoice.total_amount = Decimal(str(total_amount))
                    target_invoice.amount = Decimal(str(total_amount))
                    target_invoice.amount_paid = Decimal(str(paid_amount))
                    target_invoice.balance = Decimal(str(outstanding))
                    target_invoice.status = status
                    target_invoice.currency = inv_data.get("currency", "NGN")
                    target_invoice.last_synced_at = datetime.utcnow()

                    posting_dt = self._parse_iso_date(inv_data.get("posting_date"))
                    if posting_dt:
                        target_invoice.invoice_date = posting_dt

                    due_dt = self._parse_iso_date(inv_data.get("due_date"))
                    if due_dt:
                        target_invoice.due_date = due_dt

                    # If we found a duplicate ERPNext-only record, re-home children and delete it
                    if duplicate_invoice:
                        for payment in list(duplicate_invoice.payments):
                            payment.invoice_id = target_invoice.id
                        for credit_note in list(duplicate_invoice.credit_notes):
                            credit_note.invoice_id = target_invoice.id
                        self.db.delete(duplicate_invoice)
                    self.increment_updated()
                else:
                    invoice = Invoice(
                        erpnext_id=erpnext_id,
                        source=InvoiceSource.ERPNEXT,
                        customer_id=customer_id,
                        invoice_number=erpnext_id,
                        total_amount=total_amount,
                        amount=total_amount,
                        amount_paid=paid_amount,
                        balance=outstanding,
                        status=status,
                        currency=inv_data.get("currency", "NGN"),
                        invoice_date=datetime.utcnow(),
                    )

                    posting_dt = self._parse_iso_date(inv_data.get("posting_date"))
                    if posting_dt:
                        invoice.invoice_date = posting_dt

                    due_dt = self._parse_iso_date(inv_data.get("due_date"))
                    if due_dt:
                        invoice.due_date = due_dt

                    self.db.add(invoice)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_payments(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync payment entries from ERPNext."""
        self.start_sync("payments", "full" if full_sync else "incremental")

        try:
            payments = await self._fetch_all_doctype(
                client,
                "Payment Entry",
                fields=[
                    "name", "party", "party_type", "posting_date",
                    "paid_amount", "mode_of_payment", "reference_no",
                    "payment_type", "status",
                    "custom_splynx_payment_id",
                    "custom_splynx_credit_note_id",
                ],
            )

            # Track payment IDs already assigned an erpnext_id in this transaction
            assigned_payment_ids: set[int] = set()
            # Track erpnext_ids already processed in this transaction
            processed_payment_erpnext_ids: set[str] = set()

            for pay_data in payments:
                # Only process customer payments
                if pay_data.get("party_type") != "Customer":
                    continue

                erpnext_id = pay_data.get("name")

                # Skip if this erpnext_id was already processed in this batch
                if erpnext_id in processed_payment_erpnext_ids:
                    continue
                processed_payment_erpnext_ids.add(erpnext_id)
                custom_splynx_payment_id = self._safe_int(pay_data.get("custom_splynx_payment_id"))
                splynx_payment = (
                    self.db.query(Payment)
                    .filter(Payment.splynx_id == custom_splynx_payment_id)
                    .first()
                    if custom_splynx_payment_id
                    else None
                )

                existing_erpnext = self.db.query(Payment).filter(
                    Payment.erpnext_id == erpnext_id
                ).first()

                # Find customer
                customer_erpnext_id = pay_data.get("party")
                customer = self.db.query(Customer).filter(
                    Customer.erpnext_id == customer_erpnext_id
                ).first()
                customer_id = customer.id if customer else None

                amount = float(pay_data.get("paid_amount", 0) or 0)

                # Map payment method
                mode = (pay_data.get("mode_of_payment", "") or "").lower()
                method_map = {
                    "cash": PaymentMethod.CASH,
                    "bank transfer": PaymentMethod.BANK_TRANSFER,
                    "credit card": PaymentMethod.CARD,
                    "debit card": PaymentMethod.CARD,
                }
                payment_method = PaymentMethod.OTHER
                for key, value in method_map.items():
                    if key in mode:
                        payment_method = value
                        break

                # Determine target payment, handling conflicts between splynx linkage and existing erpnext record
                target_payment: Optional[Payment] = None
                duplicate_payment: Optional[Payment] = None

                if splynx_payment and existing_erpnext:
                    if splynx_payment.id == existing_erpnext.id:
                        # Same payment - use it
                        target_payment = splynx_payment
                    elif existing_erpnext.source == PaymentSource.ERPNEXT:
                        # Existing ERPNext-only record can be merged into Splynx record
                        target_payment = splynx_payment
                        duplicate_payment = existing_erpnext
                    else:
                        # Conflict: existing_erpnext is a Splynx payment with this erpnext_id
                        # Use existing_erpnext to avoid unique constraint violation
                        import structlog
                        logger = structlog.get_logger()
                        logger.warning(
                            "erpnext_splynx_payment_linkage_conflict",
                            erpnext_id=erpnext_id,
                            custom_splynx_id=custom_splynx_payment_id,
                            existing_payment_id=existing_erpnext.id,
                            linked_splynx_payment_id=splynx_payment.id,
                        )
                        target_payment = existing_erpnext
                elif splynx_payment:
                    target_payment = splynx_payment
                elif existing_erpnext:
                    target_payment = existing_erpnext

                # Soft-match if custom link missing: same amount, customer, and date
                if not target_payment:
                    posting_dt = self._parse_iso_date(pay_data.get("posting_date"))
                    if posting_dt and customer_id:
                        # Exclude payments already assigned in this transaction or already having an erpnext_id
                        target_payment = (
                            self.db.query(Payment)
                            .filter(
                                Payment.source == PaymentSource.SPLYNX,
                                Payment.customer_id == customer_id,
                                Payment.amount == Decimal(str(amount)),
                                func.date(Payment.payment_date) == posting_dt.date(),
                                Payment.erpnext_id.is_(None),
                                ~Payment.id.in_(assigned_payment_ids) if assigned_payment_ids else True,
                            )
                            .first()
                        )

                if target_payment:
                    # Track this payment as assigned to avoid duplicate erpnext_id assignments
                    assigned_payment_ids.add(target_payment.id)

                    # If we're merging with a duplicate, clear its erpnext_id first to avoid constraint violation
                    if duplicate_payment:
                        duplicate_payment.erpnext_id = None
                        self.db.flush()  # Flush the NULL assignment before setting the new value

                    target_payment.erpnext_id = erpnext_id
                    target_payment.customer_id = customer_id
                    target_payment.amount = Decimal(str(amount))
                    target_payment.payment_method = payment_method
                    target_payment.transaction_reference = pay_data.get("reference_no")
                    target_payment.last_synced_at = datetime.utcnow()

                    posting_dt = self._parse_iso_date(pay_data.get("posting_date"))
                    if posting_dt:
                        target_payment.payment_date = posting_dt

                    # Map ERPNext status to our enum if present
                    status_str = (pay_data.get("status", "") or "").lower()
                    status_map = {
                        "submitted": PaymentStatus.COMPLETED,
                        "completed": PaymentStatus.COMPLETED,
                        "draft": PaymentStatus.PENDING,
                        "cancelled": PaymentStatus.FAILED,
                        "failed": PaymentStatus.FAILED,
                    }
                    if status_str in status_map:
                        target_payment.status = status_map[status_str]

                    # Delete the duplicate ERPNext-only payment after merging
                    if duplicate_payment:
                        self.db.delete(duplicate_payment)

                    self.increment_updated()
                else:
                    payment = Payment(
                        erpnext_id=erpnext_id,
                        source=PaymentSource.ERPNEXT,
                        customer_id=customer_id,
                        amount=amount,
                        payment_method=payment_method,
                        receipt_number=erpnext_id,
                        transaction_reference=pay_data.get("reference_no"),
                        payment_date=datetime.utcnow(),
                    )

                    posting_dt = self._parse_iso_date(pay_data.get("posting_date"))
                    if posting_dt:
                        payment.payment_date = posting_dt

                    self.db.add(payment)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_expenses(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync Expense Claims from ERPNext with full fields and FK relationships."""
        self.start_sync("expenses", "full" if full_sync else "incremental")

        try:
            # Fetch all expense claims with full fields
            expense_claims = await self._fetch_all_doctype(
                client,
                "Expense Claim",
                fields=["*"],
            )

            # Pre-fetch employees by erpnext_id for FK linking
            employees_by_erpnext_id = {
                e.erpnext_id: e.id
                for e in self.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).all()
            }

            # Pre-fetch projects by erpnext_id for FK linking
            from app.models.project import Project
            projects_by_erpnext_id = {
                p.erpnext_id: p.id
                for p in self.db.query(Project).filter(Project.erpnext_id.isnot(None)).all()
            }

            # OPTIMIZATION: Batch fetch Expense Claim Detail child records to avoid N+1
            # This fetches all expense details in one API call instead of N individual calls
            expense_details: Dict[str, List[Dict[str, Any]]] = {}
            try:
                all_details = await self._fetch_all_doctype(
                    client,
                    "Expense Claim Detail",
                    fields=["parent", "expense_type", "description"],
                )
                # Group by parent expense claim
                for detail in all_details:
                    parent = detail.get("parent")
                    if parent:
                        if parent not in expense_details:
                            expense_details[parent] = []
                        expense_details[parent].append(detail)
                logger.info("expense_details_prefetched", total=len(all_details), unique_claims=len(expense_details))
            except Exception as e:
                logger.warning("failed_to_prefetch_expense_details", error=str(e))
                # Continue without details - N+1 fallback disabled for performance

            # Helper for Decimal conversion
            def to_decimal(val: Any) -> Decimal:
                return Decimal(str(val or 0))

            batch_size = 500
            for i, exp_data in enumerate(expense_claims, 1):
                erpnext_id = exp_data.get("name")
                existing = self.db.query(Expense).filter(Expense.erpnext_id == erpnext_id).first()

                # Map status
                status_str = (exp_data.get("status", "") or "").lower()
                status_map = {
                    "draft": ExpenseStatus.DRAFT,
                    "pending approval": ExpenseStatus.PENDING,
                    "approved": ExpenseStatus.APPROVED,
                    "rejected": ExpenseStatus.REJECTED,
                    "paid": ExpenseStatus.PAID,
                    "cancelled": ExpenseStatus.CANCELLED,
                    "unpaid": ExpenseStatus.APPROVED,  # Approved but not yet paid
                }
                status = status_map.get(status_str, ExpenseStatus.DRAFT)

                # Link to employee
                erpnext_employee = exp_data.get("employee")
                employee_id = employees_by_erpnext_id.get(erpnext_employee) if erpnext_employee else None

                # Link to project
                erpnext_project = exp_data.get("project")
                project_id = projects_by_erpnext_id.get(erpnext_project) if erpnext_project else None

                # Get expense_type and description from pre-fetched child records (N+1 fix)
                expense_type = None
                description = None
                claim_details = expense_details.get(erpnext_id, [])
                if claim_details:
                    # Get expense types, join if multiple
                    expense_types = [d.get("expense_type") for d in claim_details if d.get("expense_type")]
                    expense_type = ", ".join(set(expense_types)) if expense_types else None
                    # Get descriptions
                    descriptions = [d.get("description") for d in claim_details if d.get("description")]
                    description = "; ".join(descriptions) if descriptions else None

                if existing:
                    # Employee
                    existing.employee_id = employee_id
                    existing.employee_name = exp_data.get("employee_name")
                    existing.erpnext_employee = erpnext_employee

                    # Project
                    existing.project_id = project_id
                    existing.erpnext_project = erpnext_project

                    # Expense details
                    existing.expense_type = expense_type
                    existing.description = description
                    existing.remark = exp_data.get("remark")

                    # Amounts
                    existing.total_claimed_amount = to_decimal(exp_data.get("total_claimed_amount"))
                    existing.total_sanctioned_amount = to_decimal(exp_data.get("total_sanctioned_amount"))
                    existing.total_amount_reimbursed = to_decimal(exp_data.get("total_amount_reimbursed"))
                    existing.total_advance_amount = to_decimal(exp_data.get("total_advance_amount"))
                    existing.amount = to_decimal(exp_data.get("total_claimed_amount"))

                    # Taxes
                    existing.total_taxes_and_charges = to_decimal(exp_data.get("total_taxes_and_charges"))

                    # Categorization
                    existing.cost_center = exp_data.get("cost_center")
                    existing.company = exp_data.get("company")

                    # Accounting
                    existing.payable_account = exp_data.get("payable_account")
                    existing.mode_of_payment = exp_data.get("mode_of_payment")

                    # Approval
                    existing.approval_status = exp_data.get("approval_status")
                    existing.expense_approver = exp_data.get("expense_approver")

                    # Status
                    existing.status = status
                    existing.is_paid = exp_data.get("is_paid", 0) == 1
                    existing.docstatus = exp_data.get("docstatus", 0)

                    # Task
                    existing.task = exp_data.get("task")

                    existing.last_synced_at = datetime.utcnow()

                    # Dates
                    if exp_data.get("posting_date"):
                        try:
                            existing.posting_date = datetime.fromisoformat(exp_data["posting_date"])
                            existing.expense_date = existing.posting_date
                        except (ValueError, TypeError):
                            pass

                    if exp_data.get("clearance_date"):
                        try:
                            existing.clearance_date = datetime.fromisoformat(exp_data["clearance_date"])
                        except (ValueError, TypeError):
                            pass

                    self.increment_updated()
                else:
                    expense = Expense(
                        erpnext_id=erpnext_id,

                        # Employee
                        employee_id=employee_id,
                        employee_name=exp_data.get("employee_name"),
                        erpnext_employee=erpnext_employee,

                        # Project
                        project_id=project_id,
                        erpnext_project=erpnext_project,

                        # Expense details
                        expense_type=expense_type,
                        description=description,
                        remark=exp_data.get("remark"),

                        # Amounts
                        total_claimed_amount=to_decimal(exp_data.get("total_claimed_amount")),
                        total_sanctioned_amount=to_decimal(exp_data.get("total_sanctioned_amount")),
                        total_amount_reimbursed=to_decimal(exp_data.get("total_amount_reimbursed")),
                        total_advance_amount=to_decimal(exp_data.get("total_advance_amount")),
                        amount=to_decimal(exp_data.get("total_claimed_amount")),

                        # Taxes
                        total_taxes_and_charges=to_decimal(exp_data.get("total_taxes_and_charges")),

                        # Categorization
                        cost_center=exp_data.get("cost_center"),
                        company=exp_data.get("company"),

                        # Accounting
                        payable_account=exp_data.get("payable_account"),
                        mode_of_payment=exp_data.get("mode_of_payment"),

                        # Approval
                        approval_status=exp_data.get("approval_status"),
                        expense_approver=exp_data.get("expense_approver"),

                        # Status
                        status=status,
                        is_paid=exp_data.get("is_paid", 0) == 1,
                        docstatus=exp_data.get("docstatus", 0),

                        # Task
                        task=exp_data.get("task"),
                    )

                    # Dates
                    if exp_data.get("posting_date"):
                        try:
                            expense.posting_date = datetime.fromisoformat(exp_data["posting_date"])
                            expense.expense_date = expense.posting_date
                        except (ValueError, TypeError):
                            expense.expense_date = datetime.utcnow()
                    else:
                        expense.expense_date = datetime.utcnow()

                    if exp_data.get("clearance_date"):
                        try:
                            expense.clearance_date = datetime.fromisoformat(exp_data["clearance_date"])
                        except (ValueError, TypeError):
                            pass

                    self.db.add(expense)
                    self.increment_created()

                # Batch commit
                if i % batch_size == 0:
                    self.db.commit()
                    logger.debug("expenses_batch_committed", processed=i, total=len(expense_claims))

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_hd_tickets(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync HD Tickets (Help Desk) from ERPNext with full FK relationships."""
        self.start_sync("hd_tickets", "full" if full_sync else "incremental")

        try:
            tickets = await self._fetch_all_doctype(
                client,
                "HD Ticket",
                fields=["*"],
            )

            # Pre-fetch customers by email and erpnext_id for linking
            customers_by_email = {
                c.email.lower(): c.id
                for c in self.db.query(Customer).filter(Customer.email.isnot(None)).all()
                if c.email
            }
            customers_by_erpnext_id = {
                c.erpnext_id: c.id
                for c in self.db.query(Customer).filter(Customer.erpnext_id.isnot(None)).all()
            }

            # Pre-fetch employees by email for linking
            employees_by_email = {
                e.email.lower(): e.id
                for e in self.db.query(Employee).filter(Employee.email.isnot(None)).all()
                if e.email
            }

            # Pre-fetch projects by erpnext_id for linking
            from app.models.project import Project
            projects_by_erpnext_id = {
                p.erpnext_id: p.id
                for p in self.db.query(Project).filter(Project.erpnext_id.isnot(None)).all()
            }

            batch_size = 500
            for i, ticket_data in enumerate(tickets, 1):
                erpnext_id = str(ticket_data.get("name"))
                existing = self.db.query(Ticket).filter(Ticket.erpnext_id == erpnext_id).first()

                # Map status
                status_str = (ticket_data.get("custom_ticket_status") or ticket_data.get("status", "") or "").lower()
                status_map = {
                    "open": TicketStatus.OPEN,
                    "replied": TicketStatus.REPLIED,
                    "resolved": TicketStatus.RESOLVED,
                    "closed": TicketStatus.CLOSED,
                    "on hold": TicketStatus.ON_HOLD,
                }
                status = status_map.get(status_str, TicketStatus.OPEN)

                # Map priority
                priority_str = (ticket_data.get("priority", "") or "").lower()
                priority_map = {
                    "low": TicketPriority.LOW,
                    "medium": TicketPriority.MEDIUM,
                    "high": TicketPriority.HIGH,
                    "urgent": TicketPriority.URGENT,
                }
                priority = priority_map.get(priority_str, TicketPriority.MEDIUM)

                # Extract data
                customer_email = ticket_data.get("custom_email")
                customer_phone = ticket_data.get("custom_phone")
                customer_name = ticket_data.get("custom_customer_name")
                region = ticket_data.get("custom_region")
                base_station = ticket_data.get("custom_base_station")
                raised_by = ticket_data.get("raised_by")
                owner_email = ticket_data.get("owner")
                erpnext_customer = ticket_data.get("customer")
                erpnext_project = ticket_data.get("project")
                resolution_team = ticket_data.get("custom_resolution_team")
                agent_email = ticket_data.get("agent")  # Assigned agent email

                # Link to customer (try erpnext_id first, then email)
                customer_id = None
                if erpnext_customer:
                    customer_id = customers_by_erpnext_id.get(erpnext_customer)
                if not customer_id and customer_email:
                    customer_id = customers_by_email.get(customer_email.lower())

                # Link to employee (who raised the ticket)
                employee_id = None
                if raised_by:
                    employee_id = employees_by_email.get(raised_by.lower())

                # Link to assigned employee (agent)
                assigned_employee_id = None
                if agent_email:
                    assigned_employee_id = employees_by_email.get(agent_email.lower())

                # Link to project
                project_id = None
                if erpnext_project:
                    project_id = projects_by_erpnext_id.get(erpnext_project)

                if existing:
                    # Basic info
                    existing.subject = ticket_data.get("subject")
                    existing.description = ticket_data.get("description")
                    existing.ticket_type = ticket_data.get("ticket_type")
                    existing.issue_type = ticket_data.get("ticket_type")
                    existing.status = status
                    existing.priority = priority

                    # FK relationships
                    existing.customer_id = customer_id
                    existing.employee_id = employee_id
                    existing.assigned_employee_id = assigned_employee_id
                    existing.project_id = project_id
                    existing.erpnext_customer = erpnext_customer
                    existing.erpnext_project = erpnext_project

                    # Assignment
                    existing.raised_by = raised_by
                    existing.owner_email = owner_email
                    existing.assigned_to = agent_email
                    existing.resolution_team = resolution_team
                    existing.company = ticket_data.get("company")

                    # Customer info
                    existing.customer_email = customer_email
                    existing.customer_phone = customer_phone
                    existing.customer_name = customer_name

                    # Location
                    existing.region = region
                    existing.base_station = base_station

                    # SLA tracking
                    existing.agreement_status = ticket_data.get("agreement_status")

                    # Resolution
                    existing.resolution = ticket_data.get("resolution")
                    existing.resolution_details = ticket_data.get("resolution_details")

                    # Feedback
                    existing.feedback_rating = ticket_data.get("feedback_rating")
                    existing.feedback_text = ticket_data.get("feedback_text")

                    existing.last_synced_at = datetime.utcnow()

                    # Date fields
                    date_fields = [
                        ("opening_date", "opening_date"),
                        ("resolution_date", "resolution_date"),
                        ("response_by", "response_by"),
                        ("resolution_by", "resolution_by"),
                        ("first_responded_on", "first_responded_on"),
                    ]
                    for model_field, data_field in date_fields:
                        if ticket_data.get(data_field):
                            try:
                                setattr(existing, model_field, datetime.fromisoformat(str(ticket_data[data_field])))
                            except (ValueError, TypeError):
                                pass

                    self.increment_updated()
                else:
                    ticket = Ticket(
                        erpnext_id=erpnext_id,
                        source=TicketSource.ERPNEXT,
                        ticket_number=f"HD-{erpnext_id}",

                        # Basic info
                        subject=ticket_data.get("subject"),
                        description=ticket_data.get("description"),
                        ticket_type=ticket_data.get("ticket_type"),
                        issue_type=ticket_data.get("ticket_type"),
                        status=status,
                        priority=priority,

                        # FK relationships
                        customer_id=customer_id,
                        employee_id=employee_id,
                        assigned_employee_id=assigned_employee_id,
                        project_id=project_id,
                        erpnext_customer=erpnext_customer,
                        erpnext_project=erpnext_project,

                        # Assignment
                        raised_by=raised_by,
                        owner_email=owner_email,
                        assigned_to=agent_email,
                        resolution_team=resolution_team,
                        company=ticket_data.get("company"),

                        # Customer info
                        customer_email=customer_email,
                        customer_phone=customer_phone,
                        customer_name=customer_name,

                        # Location
                        region=region,
                        base_station=base_station,

                        # SLA tracking
                        agreement_status=ticket_data.get("agreement_status"),

                        # Resolution
                        resolution=ticket_data.get("resolution"),
                        resolution_details=ticket_data.get("resolution_details"),

                        # Feedback
                        feedback_rating=ticket_data.get("feedback_rating"),
                        feedback_text=ticket_data.get("feedback_text"),
                    )

                    # Date fields
                    date_fields = [
                        ("opening_date", "opening_date"),
                        ("resolution_date", "resolution_date"),
                        ("response_by", "response_by"),
                        ("resolution_by", "resolution_by"),
                        ("first_responded_on", "first_responded_on"),
                    ]
                    for model_field, data_field in date_fields:
                        if ticket_data.get(data_field):
                            try:
                                setattr(ticket, model_field, datetime.fromisoformat(str(ticket_data[data_field])))
                            except (ValueError, TypeError):
                                pass

                    if not ticket.opening_date:
                        ticket.opening_date = datetime.utcnow()

                    self.db.add(ticket)
                    self.increment_created()

                # Batch commit
                if i % batch_size == 0:
                    self.db.commit()
                    logger.debug("hd_tickets_batch_committed", processed=i, total=len(tickets))

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_projects(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync projects from ERPNext with full fields and FK relationships."""
        self.start_sync("projects", "full" if full_sync else "incremental")

        try:
            # Fetch all fields
            projects = await self._fetch_all_doctype(
                client,
                "Project",
                fields=["*"],
            )

            # Pre-fetch customers by erpnext_id for FK linking
            customers_by_erpnext_id = {
                c.erpnext_id: c.id
                for c in self.db.query(Customer).filter(Customer.erpnext_id.isnot(None)).all()
            }

            # Pre-fetch employees by email for project manager FK
            employees_by_email = {
                e.email: e.id
                for e in self.db.query(Employee).filter(Employee.email.isnot(None)).all()
            }

            batch_size = 500
            for i, proj_data in enumerate(projects, 1):
                erpnext_id = proj_data.get("name")
                existing = self.db.query(Project).filter(Project.erpnext_id == erpnext_id).first()

                # Map status
                status_str = (proj_data.get("status", "") or "").lower()
                status_map = {
                    "open": ProjectStatus.OPEN,
                    "completed": ProjectStatus.COMPLETED,
                    "cancelled": ProjectStatus.CANCELLED,
                    "on hold": ProjectStatus.ON_HOLD,
                }
                status = status_map.get(status_str, ProjectStatus.OPEN)

                # Map priority
                priority_str = (proj_data.get("priority", "") or "").lower()
                priority_map = {
                    "low": ProjectPriority.LOW,
                    "medium": ProjectPriority.MEDIUM,
                    "high": ProjectPriority.HIGH,
                }
                priority = priority_map.get(priority_str, ProjectPriority.MEDIUM)

                # Link to customer
                erpnext_customer = proj_data.get("customer")
                customer_id = customers_by_erpnext_id.get(erpnext_customer) if erpnext_customer else None

                # Link to project manager (by user email - try to match by employee email)
                project_manager_email = proj_data.get("project_manager") or proj_data.get("owner")
                project_manager_id = employees_by_email.get(project_manager_email) if project_manager_email else None

                # Helper for Decimal conversion
                def to_decimal(val: Any) -> Decimal:
                    return Decimal(str(val or 0))

                if existing:
                    existing.project_name = proj_data.get("project_name", "")
                    existing.project_type = proj_data.get("project_type")
                    existing.status = status
                    existing.priority = priority
                    existing.department = proj_data.get("department")
                    existing.company = proj_data.get("company")
                    existing.cost_center = proj_data.get("cost_center")

                    # FK relationships
                    existing.customer_id = customer_id
                    existing.erpnext_customer = erpnext_customer
                    existing.erpnext_sales_order = proj_data.get("sales_order")
                    existing.project_manager_id = project_manager_id

                    # Progress
                    existing.percent_complete = to_decimal(proj_data.get("percent_complete"))
                    existing.percent_complete_method = proj_data.get("percent_complete_method")
                    existing.is_active = proj_data.get("is_active", "Yes")

                    # Time tracking
                    existing.actual_time = to_decimal(proj_data.get("actual_time"))
                    existing.total_consumed_material_cost = to_decimal(proj_data.get("total_consumed_material_cost"))

                    # Costing
                    existing.estimated_costing = to_decimal(proj_data.get("estimated_costing"))
                    existing.total_costing_amount = to_decimal(proj_data.get("total_costing_amount"))
                    existing.total_expense_claim = to_decimal(proj_data.get("total_expense_claim"))
                    existing.total_purchase_cost = to_decimal(proj_data.get("total_purchase_cost"))

                    # Revenue
                    existing.total_sales_amount = to_decimal(proj_data.get("total_sales_amount"))
                    existing.total_billable_amount = to_decimal(proj_data.get("total_billable_amount"))
                    existing.total_billed_amount = to_decimal(proj_data.get("total_billed_amount"))

                    # Margin
                    existing.gross_margin = to_decimal(proj_data.get("gross_margin"))
                    existing.per_gross_margin = to_decimal(proj_data.get("per_gross_margin"))

                    # Billing
                    existing.collect_progress = proj_data.get("collect_progress", 0) == 1
                    existing.frequency = proj_data.get("frequency")
                    existing.message = proj_data.get("message")

                    # Notes
                    existing.notes = proj_data.get("notes")

                    existing.last_synced_at = datetime.utcnow()

                    # Date fields
                    date_fields = ["expected_start_date", "expected_end_date", "actual_start_date", "actual_end_date"]
                    for date_field in date_fields:
                        if proj_data.get(date_field):
                            try:
                                setattr(existing, date_field, datetime.fromisoformat(proj_data[date_field]))
                            except (ValueError, TypeError):
                                pass

                    # Time fields (datetime)
                    for time_field in ["from_time", "to_time"]:
                        if proj_data.get(time_field):
                            try:
                                setattr(existing, time_field, datetime.fromisoformat(proj_data[time_field]))
                            except (ValueError, TypeError):
                                pass

                    self.increment_updated()
                else:
                    project = Project(
                        erpnext_id=erpnext_id,
                        project_name=proj_data.get("project_name", ""),
                        project_type=proj_data.get("project_type"),
                        status=status,
                        priority=priority,
                        department=proj_data.get("department"),
                        company=proj_data.get("company"),
                        cost_center=proj_data.get("cost_center"),

                        # FK relationships
                        customer_id=customer_id,
                        erpnext_customer=erpnext_customer,
                        erpnext_sales_order=proj_data.get("sales_order"),
                        project_manager_id=project_manager_id,

                        # Progress
                        percent_complete=to_decimal(proj_data.get("percent_complete")),
                        percent_complete_method=proj_data.get("percent_complete_method"),
                        is_active=proj_data.get("is_active", "Yes"),

                        # Time tracking
                        actual_time=to_decimal(proj_data.get("actual_time")),
                        total_consumed_material_cost=to_decimal(proj_data.get("total_consumed_material_cost")),

                        # Costing
                        estimated_costing=to_decimal(proj_data.get("estimated_costing")),
                        total_costing_amount=to_decimal(proj_data.get("total_costing_amount")),
                        total_expense_claim=to_decimal(proj_data.get("total_expense_claim")),
                        total_purchase_cost=to_decimal(proj_data.get("total_purchase_cost")),

                        # Revenue
                        total_sales_amount=to_decimal(proj_data.get("total_sales_amount")),
                        total_billable_amount=to_decimal(proj_data.get("total_billable_amount")),
                        total_billed_amount=to_decimal(proj_data.get("total_billed_amount")),

                        # Margin
                        gross_margin=to_decimal(proj_data.get("gross_margin")),
                        per_gross_margin=to_decimal(proj_data.get("per_gross_margin")),

                        # Billing
                        collect_progress=proj_data.get("collect_progress", 0) == 1,
                        frequency=proj_data.get("frequency"),
                        message=proj_data.get("message"),

                        # Notes
                        notes=proj_data.get("notes"),
                    )

                    # Date fields
                    date_fields = ["expected_start_date", "expected_end_date", "actual_start_date", "actual_end_date"]
                    for date_field in date_fields:
                        if proj_data.get(date_field):
                            try:
                                setattr(project, date_field, datetime.fromisoformat(proj_data[date_field]))
                            except (ValueError, TypeError):
                                pass

                    # Time fields
                    for time_field in ["from_time", "to_time"]:
                        if proj_data.get(time_field):
                            try:
                                setattr(project, time_field, datetime.fromisoformat(proj_data[time_field]))
                            except (ValueError, TypeError):
                                pass

                    self.db.add(project)
                    self.increment_created()

                # Batch commit
                if i % batch_size == 0:
                    self.db.commit()
                    logger.debug("projects_batch_committed", processed=i, total=len(projects))

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_projects_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Projects with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_projects(client, full_sync)

    async def sync_customers_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Customers with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_customers(client, full_sync)

    async def sync_invoices_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Invoices with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_invoices(client, full_sync)

    async def sync_payments_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Payments with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_payments(client, full_sync)

    async def sync_expenses_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Expenses with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_expenses(client, full_sync)

    # ============= ACCOUNTING SYNC METHODS =============

    async def sync_bank_accounts(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync bank accounts from ERPNext."""
        self.start_sync("bank_accounts", "full" if full_sync else "incremental")

        try:
            bank_accounts = await self._fetch_all_doctype(
                client,
                "Bank Account",
                fields=["*"],  # Get all fields to avoid missing field errors
            )

            for ba_data in bank_accounts:
                erpnext_id = ba_data.get("name")
                existing = self.db.query(BankAccount).filter(BankAccount.erpnext_id == erpnext_id).first()

                if existing:
                    existing.account_name = ba_data.get("account_name", "")
                    existing.bank = ba_data.get("bank")
                    existing.bank_account_no = ba_data.get("bank_account_no")
                    existing.account = ba_data.get("account")
                    existing.company = ba_data.get("company")
                    existing.currency = ba_data.get("currency", "NGN")
                    existing.is_company_account = ba_data.get("is_company_account", 1) == 1
                    existing.is_default = ba_data.get("is_default", 0) == 1
                    existing.disabled = ba_data.get("disabled", 0) == 1
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    bank_account = BankAccount(
                        erpnext_id=erpnext_id,
                        account_name=ba_data.get("account_name", ""),
                        bank=ba_data.get("bank"),
                        bank_account_no=ba_data.get("bank_account_no"),
                        account=ba_data.get("account"),
                        company=ba_data.get("company"),
                        currency=ba_data.get("currency", "NGN"),
                        is_company_account=ba_data.get("is_company_account", 1) == 1,
                        is_default=ba_data.get("is_default", 0) == 1,
                        disabled=ba_data.get("disabled", 0) == 1,
                    )
                    self.db.add(bank_account)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_accounts(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync chart of accounts from ERPNext."""
        self.start_sync("accounts", "full" if full_sync else "incremental")

        try:
            accounts = await self._fetch_all_doctype(
                client,
                "Account",
                fields=["*"],  # Get all fields
            )

            for acc_data in accounts:
                erpnext_id = acc_data.get("name")
                existing = self.db.query(Account).filter(Account.erpnext_id == erpnext_id).first()

                # Map root type
                root_type_str = (acc_data.get("root_type", "") or "").lower()
                root_type_map = {
                    "asset": AccountType.ASSET,
                    "liability": AccountType.LIABILITY,
                    "equity": AccountType.EQUITY,
                    "income": AccountType.INCOME,
                    "expense": AccountType.EXPENSE,
                }
                root_type = root_type_map.get(root_type_str)

                if existing:
                    existing.account_name = acc_data.get("account_name", "")
                    existing.account_number = acc_data.get("account_number")
                    existing.parent_account = acc_data.get("parent_account")
                    existing.root_type = root_type
                    existing.account_type = acc_data.get("account_type")
                    existing.company = acc_data.get("company")
                    existing.is_group = acc_data.get("is_group", 0) == 1
                    existing.disabled = acc_data.get("disabled", 0) == 1
                    existing.balance_must_be = acc_data.get("balance_must_be")
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    account = Account(
                        erpnext_id=erpnext_id,
                        account_name=acc_data.get("account_name", ""),
                        account_number=acc_data.get("account_number"),
                        parent_account=acc_data.get("parent_account"),
                        root_type=root_type,
                        account_type=acc_data.get("account_type"),
                        company=acc_data.get("company"),
                        is_group=acc_data.get("is_group", 0) == 1,
                        disabled=acc_data.get("disabled", 0) == 1,
                        balance_must_be=acc_data.get("balance_must_be"),
                    )
                    self.db.add(account)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_journal_entries(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync journal entries from ERPNext."""
        self.start_sync("journal_entries", "full" if full_sync else "incremental")

        try:
            entries = await self._fetch_all_doctype(
                client,
                "Journal Entry",
                fields=["*"],  # Get all fields
            )

            batch_size = 500
            for i, entry_data in enumerate(entries, 1):
                erpnext_id = entry_data.get("name")
                existing = self.db.query(JournalEntry).filter(JournalEntry.erpnext_id == erpnext_id).first()

                # Map voucher type
                vtype_str = (entry_data.get("voucher_type", "") or "").lower().replace(" ", "_")
                vtype_map = {
                    "journal_entry": JournalEntryType.JOURNAL_ENTRY,
                    "bank_entry": JournalEntryType.BANK_ENTRY,
                    "cash_entry": JournalEntryType.CASH_ENTRY,
                    "credit_card_entry": JournalEntryType.CREDIT_CARD_ENTRY,
                    "debit_note": JournalEntryType.DEBIT_NOTE,
                    "credit_note": JournalEntryType.CREDIT_NOTE,
                    "contra_entry": JournalEntryType.CONTRA_ENTRY,
                    "excise_entry": JournalEntryType.EXCISE_ENTRY,
                    "write_off_entry": JournalEntryType.WRITE_OFF_ENTRY,
                    "opening_entry": JournalEntryType.OPENING_ENTRY,
                    "depreciation_entry": JournalEntryType.DEPRECIATION_ENTRY,
                    "exchange_rate_revaluation": JournalEntryType.EXCHANGE_RATE_REVALUATION,
                }
                voucher_type = vtype_map.get(vtype_str, JournalEntryType.JOURNAL_ENTRY)

                if existing:
                    existing.voucher_type = voucher_type
                    existing.company = entry_data.get("company")
                    existing.total_debit = Decimal(str(entry_data.get("total_debit", 0) or 0))
                    existing.total_credit = Decimal(str(entry_data.get("total_credit", 0) or 0))
                    existing.cheque_no = entry_data.get("cheque_no")
                    existing.user_remark = entry_data.get("user_remark")
                    existing.is_opening = entry_data.get("is_opening") == "Yes"
                    existing.docstatus = entry_data.get("docstatus", 0)
                    existing.last_synced_at = datetime.utcnow()

                    if entry_data.get("posting_date"):
                        try:
                            existing.posting_date = datetime.fromisoformat(entry_data["posting_date"])
                        except (ValueError, TypeError):
                            pass

                    if entry_data.get("cheque_date"):
                        try:
                            existing.cheque_date = datetime.fromisoformat(entry_data["cheque_date"])
                        except (ValueError, TypeError):
                            pass

                    self.increment_updated()
                else:
                    journal_entry = JournalEntry(
                        erpnext_id=erpnext_id,
                        voucher_type=voucher_type,
                        company=entry_data.get("company"),
                        total_debit=float(entry_data.get("total_debit", 0) or 0),
                        total_credit=float(entry_data.get("total_credit", 0) or 0),
                        cheque_no=entry_data.get("cheque_no"),
                        user_remark=entry_data.get("user_remark"),
                        is_opening=entry_data.get("is_opening") == "Yes",
                        docstatus=entry_data.get("docstatus", 0),
                    )

                    if entry_data.get("posting_date"):
                        try:
                            journal_entry.posting_date = datetime.fromisoformat(entry_data["posting_date"])
                        except (ValueError, TypeError):
                            pass

                    if entry_data.get("cheque_date"):
                        try:
                            journal_entry.cheque_date = datetime.fromisoformat(entry_data["cheque_date"])
                        except (ValueError, TypeError):
                            pass

                    self.db.add(journal_entry)
                    self.increment_created()

                # Batch commit
                if i % batch_size == 0:
                    self.db.commit()
                    logger.debug("journal_entries_batch_committed", processed=i, total=len(entries))

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_purchase_invoices(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync purchase invoices from ERPNext."""
        self.start_sync("purchase_invoices", "full" if full_sync else "incremental")

        try:
            invoices = await self._fetch_all_doctype(
                client,
                "Purchase Invoice",
                fields=["*"],  # Get all fields
            )

            for inv_data in invoices:
                erpnext_id = inv_data.get("name")
                existing = self.db.query(PurchaseInvoice).filter(PurchaseInvoice.erpnext_id == erpnext_id).first()

                # Map status
                status_str = (inv_data.get("status", "") or "").lower()
                status_map = {
                    "draft": PurchaseInvoiceStatus.DRAFT,
                    "submitted": PurchaseInvoiceStatus.SUBMITTED,
                    "paid": PurchaseInvoiceStatus.PAID,
                    "unpaid": PurchaseInvoiceStatus.UNPAID,
                    "overdue": PurchaseInvoiceStatus.OVERDUE,
                    "cancelled": PurchaseInvoiceStatus.CANCELLED,
                    "return": PurchaseInvoiceStatus.RETURN,
                }
                status = status_map.get(status_str, PurchaseInvoiceStatus.DRAFT)

                if existing:
                    existing.supplier = inv_data.get("supplier")
                    existing.supplier_name = inv_data.get("supplier_name")
                    existing.company = inv_data.get("company")
                    existing.grand_total = Decimal(str(inv_data.get("grand_total", 0) or 0))
                    existing.outstanding_amount = Decimal(str(inv_data.get("outstanding_amount", 0) or 0))
                    existing.paid_amount = Decimal(str(inv_data.get("paid_amount", 0) or 0))
                    existing.currency = inv_data.get("currency", "NGN")
                    existing.status = status
                    existing.docstatus = inv_data.get("docstatus", 0)
                    existing.last_synced_at = datetime.utcnow()

                    if inv_data.get("posting_date"):
                        try:
                            existing.posting_date = datetime.fromisoformat(inv_data["posting_date"])
                        except (ValueError, TypeError):
                            pass

                    if inv_data.get("due_date"):
                        try:
                            existing.due_date = datetime.fromisoformat(inv_data["due_date"])
                        except (ValueError, TypeError):
                            pass

                    self.increment_updated()
                else:
                    purchase_invoice = PurchaseInvoice(
                        erpnext_id=erpnext_id,
                        supplier=inv_data.get("supplier"),
                        supplier_name=inv_data.get("supplier_name"),
                        company=inv_data.get("company"),
                        grand_total=float(inv_data.get("grand_total", 0) or 0),
                        outstanding_amount=float(inv_data.get("outstanding_amount", 0) or 0),
                        paid_amount=float(inv_data.get("paid_amount", 0) or 0),
                        currency=inv_data.get("currency", "NGN"),
                        status=status,
                        docstatus=inv_data.get("docstatus", 0),
                    )

                    if inv_data.get("posting_date"):
                        try:
                            purchase_invoice.posting_date = datetime.fromisoformat(inv_data["posting_date"])
                        except (ValueError, TypeError):
                            pass

                    if inv_data.get("due_date"):
                        try:
                            purchase_invoice.due_date = datetime.fromisoformat(inv_data["due_date"])
                        except (ValueError, TypeError):
                            pass

                    self.db.add(purchase_invoice)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_gl_entries(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync general ledger entries from ERPNext."""
        self.start_sync("gl_entries", "full" if full_sync else "incremental")

        try:
            gl_entries = await self._fetch_all_doctype(
                client,
                "GL Entry",
                fields=["*"],  # Get all fields
            )

            batch_size = 500
            for i, gl_data in enumerate(gl_entries, 1):
                erpnext_id = gl_data.get("name")
                existing = self.db.query(GLEntry).filter(GLEntry.erpnext_id == erpnext_id).first()

                if existing:
                    existing.account = gl_data.get("account")
                    existing.party_type = gl_data.get("party_type")
                    existing.party = gl_data.get("party")
                    existing.debit = Decimal(str(gl_data.get("debit", 0) or 0))
                    existing.credit = Decimal(str(gl_data.get("credit", 0) or 0))
                    existing.debit_in_account_currency = Decimal(str(gl_data.get("debit_in_account_currency", 0) or 0))
                    existing.credit_in_account_currency = Decimal(str(gl_data.get("credit_in_account_currency", 0) or 0))
                    existing.voucher_type = gl_data.get("voucher_type")
                    existing.voucher_no = gl_data.get("voucher_no")
                    existing.cost_center = gl_data.get("cost_center")
                    existing.company = gl_data.get("company")
                    existing.fiscal_year = gl_data.get("fiscal_year")
                    existing.is_cancelled = gl_data.get("is_cancelled", 0) == 1
                    existing.last_synced_at = datetime.utcnow()

                    if gl_data.get("posting_date"):
                        try:
                            existing.posting_date = datetime.fromisoformat(gl_data["posting_date"])
                        except (ValueError, TypeError):
                            pass

                    self.increment_updated()
                else:
                    gl_entry = GLEntry(
                        erpnext_id=erpnext_id,
                        account=gl_data.get("account"),
                        party_type=gl_data.get("party_type"),
                        party=gl_data.get("party"),
                        debit=float(gl_data.get("debit", 0) or 0),
                        credit=float(gl_data.get("credit", 0) or 0),
                        debit_in_account_currency=float(gl_data.get("debit_in_account_currency", 0) or 0),
                        credit_in_account_currency=float(gl_data.get("credit_in_account_currency", 0) or 0),
                        voucher_type=gl_data.get("voucher_type"),
                        voucher_no=gl_data.get("voucher_no"),
                        cost_center=gl_data.get("cost_center"),
                        company=gl_data.get("company"),
                        fiscal_year=gl_data.get("fiscal_year"),
                        is_cancelled=gl_data.get("is_cancelled", 0) == 1,
                    )

                    if gl_data.get("posting_date"):
                        try:
                            gl_entry.posting_date = datetime.fromisoformat(gl_data["posting_date"])
                        except (ValueError, TypeError):
                            pass

                    self.db.add(gl_entry)
                    self.increment_created()

                # Batch commit for large datasets
                if i % batch_size == 0:
                    self.db.commit()
                    logger.debug("gl_entries_batch_committed", processed=i, total=len(gl_entries))

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_accounting_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs all accounting data."""
        async with httpx.AsyncClient(timeout=120) as client:
            await self.sync_bank_accounts(client, full_sync)
            await self.sync_accounts(client, full_sync)
            await self.sync_journal_entries(client, full_sync)
            await self.sync_purchase_invoices(client, full_sync)
            await self.sync_gl_entries(client, full_sync)

    async def sync_bank_transactions(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync bank transactions from ERPNext - imported bank statement lines."""
        self.start_sync("bank_transactions", "full" if full_sync else "incremental")

        try:
            transactions = await self._fetch_all_doctype(
                client,
                "Bank Transaction",
                fields=["*"],  # Get all fields
            )

            batch_size = 500
            for i, txn_data in enumerate(transactions, 1):
                erpnext_id = txn_data.get("name")
                existing = self.db.query(BankTransaction).filter(BankTransaction.erpnext_id == erpnext_id).first()

                # Map status
                status_str = (txn_data.get("status", "") or "").lower()
                status_map = {
                    "pending": BankTransactionStatus.PENDING,
                    "settled": BankTransactionStatus.SETTLED,
                    "unreconciled": BankTransactionStatus.UNRECONCILED,
                    "reconciled": BankTransactionStatus.RECONCILED,
                    "cancelled": BankTransactionStatus.CANCELLED,
                }
                status = status_map.get(status_str, BankTransactionStatus.PENDING)

                if existing:
                    existing.status = status
                    existing.bank_account = txn_data.get("bank_account")
                    existing.company = txn_data.get("company")
                    existing.deposit = Decimal(str(txn_data.get("deposit", 0) or 0))
                    existing.withdrawal = Decimal(str(txn_data.get("withdrawal", 0) or 0))
                    existing.currency = txn_data.get("currency", "NGN")
                    existing.description = txn_data.get("description")
                    existing.reference_number = txn_data.get("reference_number")
                    existing.transaction_id = txn_data.get("transaction_id")
                    existing.transaction_type = txn_data.get("transaction_type")
                    existing.allocated_amount = Decimal(str(txn_data.get("allocated_amount", 0) or 0))
                    existing.unallocated_amount = Decimal(str(txn_data.get("unallocated_amount", 0) or 0))
                    existing.party_type = txn_data.get("party_type")
                    existing.party = txn_data.get("party")
                    existing.bank_party_name = txn_data.get("bank_party_name")
                    existing.bank_party_account_number = txn_data.get("bank_party_account_number")
                    existing.bank_party_iban = txn_data.get("bank_party_iban")
                    existing.docstatus = txn_data.get("docstatus", 0)
                    existing.last_synced_at = datetime.utcnow()

                    if txn_data.get("date"):
                        try:
                            existing.date = datetime.fromisoformat(txn_data["date"])
                        except (ValueError, TypeError):
                            pass

                    self.increment_updated()
                else:
                    bank_txn = BankTransaction(
                        erpnext_id=erpnext_id,
                        status=status,
                        bank_account=txn_data.get("bank_account"),
                        company=txn_data.get("company"),
                        deposit=float(txn_data.get("deposit", 0) or 0),
                        withdrawal=float(txn_data.get("withdrawal", 0) or 0),
                        currency=txn_data.get("currency", "NGN"),
                        description=txn_data.get("description"),
                        reference_number=txn_data.get("reference_number"),
                        transaction_id=txn_data.get("transaction_id"),
                        transaction_type=txn_data.get("transaction_type"),
                        allocated_amount=float(txn_data.get("allocated_amount", 0) or 0),
                        unallocated_amount=float(txn_data.get("unallocated_amount", 0) or 0),
                        party_type=txn_data.get("party_type"),
                        party=txn_data.get("party"),
                        bank_party_name=txn_data.get("bank_party_name"),
                        bank_party_account_number=txn_data.get("bank_party_account_number"),
                        bank_party_iban=txn_data.get("bank_party_iban"),
                        docstatus=txn_data.get("docstatus", 0),
                    )

                    if txn_data.get("date"):
                        try:
                            bank_txn.date = datetime.fromisoformat(txn_data["date"])
                        except (ValueError, TypeError):
                            pass

                    self.db.add(bank_txn)
                    self.increment_created()

                # Batch commit for large datasets
                if i % batch_size == 0:
                    self.db.commit()
                    logger.debug("bank_transactions_batch_committed", processed=i, total=len(transactions))

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_bank_transactions_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Bank Transactions with its own client."""
        async with httpx.AsyncClient(timeout=120) as client:
            await self.sync_bank_transactions(client, full_sync)

    # ============= SUPPLIER SYNC =============

    async def sync_suppliers(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync suppliers/vendors from ERPNext."""
        self.start_sync("suppliers", "full" if full_sync else "incremental")

        try:
            suppliers = await self._fetch_all_doctype(
                client,
                "Supplier",
                fields=["*"],
            )

            for sup_data in suppliers:
                erpnext_id = sup_data.get("name")
                existing = self.db.query(Supplier).filter(Supplier.erpnext_id == erpnext_id).first()

                if existing:
                    existing.supplier_name = sup_data.get("supplier_name", "")
                    existing.supplier_group = sup_data.get("supplier_group")
                    existing.supplier_type = sup_data.get("supplier_type")
                    existing.country = sup_data.get("country")
                    existing.default_currency = sup_data.get("default_currency", "NGN")
                    existing.default_bank_account = sup_data.get("default_bank_account")
                    existing.tax_id = sup_data.get("tax_id")
                    existing.tax_withholding_category = sup_data.get("tax_withholding_category")
                    existing.supplier_primary_contact = sup_data.get("supplier_primary_contact")
                    existing.supplier_primary_address = sup_data.get("supplier_primary_address")
                    existing.email_id = sup_data.get("email_id")
                    existing.mobile_no = sup_data.get("mobile_no")
                    existing.default_price_list = sup_data.get("default_price_list")
                    existing.payment_terms = sup_data.get("payment_terms")
                    existing.is_transporter = sup_data.get("is_transporter", 0) == 1
                    existing.is_internal_supplier = sup_data.get("is_internal_supplier", 0) == 1
                    existing.disabled = sup_data.get("disabled", 0) == 1
                    existing.is_frozen = sup_data.get("is_frozen", 0) == 1
                    existing.on_hold = sup_data.get("on_hold", 0) == 1
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    supplier = Supplier(
                        erpnext_id=erpnext_id,
                        supplier_name=sup_data.get("supplier_name", ""),
                        supplier_group=sup_data.get("supplier_group"),
                        supplier_type=sup_data.get("supplier_type"),
                        country=sup_data.get("country"),
                        default_currency=sup_data.get("default_currency", "NGN"),
                        default_bank_account=sup_data.get("default_bank_account"),
                        tax_id=sup_data.get("tax_id"),
                        tax_withholding_category=sup_data.get("tax_withholding_category"),
                        supplier_primary_contact=sup_data.get("supplier_primary_contact"),
                        supplier_primary_address=sup_data.get("supplier_primary_address"),
                        email_id=sup_data.get("email_id"),
                        mobile_no=sup_data.get("mobile_no"),
                        default_price_list=sup_data.get("default_price_list"),
                        payment_terms=sup_data.get("payment_terms"),
                        is_transporter=sup_data.get("is_transporter", 0) == 1,
                        is_internal_supplier=sup_data.get("is_internal_supplier", 0) == 1,
                        disabled=sup_data.get("disabled", 0) == 1,
                        is_frozen=sup_data.get("is_frozen", 0) == 1,
                        on_hold=sup_data.get("on_hold", 0) == 1,
                    )
                    self.db.add(supplier)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_suppliers_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Suppliers with its own client."""
        async with httpx.AsyncClient(timeout=120) as client:
            await self.sync_suppliers(client, full_sync)

    # ============= MODE OF PAYMENT SYNC =============

    async def sync_modes_of_payment(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync payment modes from ERPNext (Cash, Bank Transfer, etc.)."""
        self.start_sync("modes_of_payment", "full" if full_sync else "incremental")

        try:
            modes = await self._fetch_all_doctype(
                client,
                "Mode of Payment",
                fields=["*"],
            )

            for mode_data in modes:
                erpnext_id = mode_data.get("name")
                existing = self.db.query(ModeOfPayment).filter(ModeOfPayment.erpnext_id == erpnext_id).first()

                # Map type
                type_str = (mode_data.get("type", "") or "").lower()
                type_map = {
                    "cash": PaymentModeType.CASH,
                    "bank": PaymentModeType.BANK,
                    "general": PaymentModeType.GENERAL,
                }
                payment_type = type_map.get(type_str, PaymentModeType.GENERAL)

                if existing:
                    existing.mode_of_payment = str(mode_data.get("mode_of_payment") or erpnext_id)
                    existing.type = payment_type
                    existing.enabled = mode_data.get("enabled", 1) == 1
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    mode = ModeOfPayment(
                        erpnext_id=erpnext_id,
                        mode_of_payment=mode_data.get("mode_of_payment", erpnext_id),
                        type=payment_type,
                        enabled=mode_data.get("enabled", 1) == 1,
                    )
                    self.db.add(mode)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_modes_of_payment_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Modes of Payment with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_modes_of_payment(client, full_sync)

    # ============= COST CENTER SYNC =============

    async def sync_cost_centers(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync cost centers from ERPNext for departmental accounting."""
        self.start_sync("cost_centers", "full" if full_sync else "incremental")

        try:
            cost_centers = await self._fetch_all_doctype(
                client,
                "Cost Center",
                fields=["*"],
            )

            for cc_data in cost_centers:
                erpnext_id = cc_data.get("name")
                existing = self.db.query(CostCenter).filter(CostCenter.erpnext_id == erpnext_id).first()

                if existing:
                    existing.cost_center_name = cc_data.get("cost_center_name", "")
                    existing.cost_center_number = cc_data.get("cost_center_number")
                    existing.parent_cost_center = cc_data.get("parent_cost_center")
                    existing.company = cc_data.get("company")
                    existing.is_group = cc_data.get("is_group", 0) == 1
                    existing.disabled = cc_data.get("disabled", 0) == 1
                    existing.lft = cc_data.get("lft")
                    existing.rgt = cc_data.get("rgt")
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    cost_center = CostCenter(
                        erpnext_id=erpnext_id,
                        cost_center_name=cc_data.get("cost_center_name", ""),
                        cost_center_number=cc_data.get("cost_center_number"),
                        parent_cost_center=cc_data.get("parent_cost_center"),
                        company=cc_data.get("company"),
                        is_group=cc_data.get("is_group", 0) == 1,
                        disabled=cc_data.get("disabled", 0) == 1,
                        lft=cc_data.get("lft"),
                        rgt=cc_data.get("rgt"),
                    )
                    self.db.add(cost_center)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_cost_centers_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Cost Centers with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_cost_centers(client, full_sync)

    # ============= FISCAL YEAR SYNC =============

    async def sync_fiscal_years(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync fiscal years from ERPNext for accounting periods."""
        self.start_sync("fiscal_years", "full" if full_sync else "incremental")

        try:
            fiscal_years = await self._fetch_all_doctype(
                client,
                "Fiscal Year",
                fields=["*"],
            )

            for fy_data in fiscal_years:
                erpnext_id = fy_data.get("name")
                existing = self.db.query(FiscalYear).filter(FiscalYear.erpnext_id == erpnext_id).first()

                if existing:
                    existing.year = str(fy_data.get("year") or erpnext_id)
                    existing.is_short_year = fy_data.get("is_short_year", 0) == 1
                    existing.disabled = fy_data.get("disabled", 0) == 1
                    existing.auto_created = fy_data.get("auto_created", 0) == 1
                    existing.last_synced_at = datetime.utcnow()

                    if fy_data.get("year_start_date"):
                        try:
                            existing.year_start_date = datetime.fromisoformat(fy_data["year_start_date"]).date()
                        except (ValueError, TypeError):
                            pass

                    if fy_data.get("year_end_date"):
                        try:
                            existing.year_end_date = datetime.fromisoformat(fy_data["year_end_date"]).date()
                        except (ValueError, TypeError):
                            pass

                    self.increment_updated()
                else:
                    fiscal_year = FiscalYear(
                        erpnext_id=erpnext_id,
                        year=fy_data.get("year", erpnext_id),
                        is_short_year=fy_data.get("is_short_year", 0) == 1,
                        disabled=fy_data.get("disabled", 0) == 1,
                        auto_created=fy_data.get("auto_created", 0) == 1,
                    )

                    if fy_data.get("year_start_date"):
                        try:
                            fiscal_year.year_start_date = datetime.fromisoformat(fy_data["year_start_date"]).date()
                        except (ValueError, TypeError):
                            pass

                    if fy_data.get("year_end_date"):
                        try:
                            fiscal_year.year_end_date = datetime.fromisoformat(fy_data["year_end_date"]).date()
                        except (ValueError, TypeError):
                            pass

                    self.db.add(fiscal_year)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_fiscal_years_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Fiscal Years with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_fiscal_years(client, full_sync)

    # ============= EXTENDED ACCOUNTING SYNC =============

    async def sync_extended_accounting_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs all extended accounting data (Suppliers, Cost Centers, etc.)."""
        async with httpx.AsyncClient(timeout=120) as client:
            await self.sync_suppliers(client, full_sync)
            await self.sync_modes_of_payment(client, full_sync)
            await self.sync_cost_centers(client, full_sync)
            await self.sync_fiscal_years(client, full_sync)

    # ============= SALES ORDER SYNC =============

    async def sync_sales_orders(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync sales orders from ERPNext."""
        self.start_sync("sales_orders", "full" if full_sync else "incremental")

        try:
            orders = await self._fetch_all_doctype(
                client,
                "Sales Order",
                fields=["*"],
            )

            # Pre-fetch customers by erpnext_id for FK linking
            customers_by_erpnext_id = {
                c.erpnext_id: c.id
                for c in self.db.query(Customer).filter(Customer.erpnext_id.isnot(None)).all()
            }

            batch_size = 500
            for i, order_data in enumerate(orders, 1):
                erpnext_id = order_data.get("name")
                existing = self.db.query(SalesOrder).filter(SalesOrder.erpnext_id == erpnext_id).first()

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

                    self.increment_updated()
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

                    self.db.add(sales_order)
                    self.increment_created()

                # Batch commit
                if i % batch_size == 0:
                    self.db.commit()
                    logger.debug("sales_orders_batch_committed", processed=i, total=len(orders))

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_sales_orders_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Sales Orders with its own client."""
        async with httpx.AsyncClient(timeout=120) as client:
            await self.sync_sales_orders(client, full_sync)

    # ============= QUOTATION SYNC =============

    async def sync_quotations(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync quotations from ERPNext."""
        self.start_sync("quotations", "full" if full_sync else "incremental")

        try:
            quotations = await self._fetch_all_doctype(
                client,
                "Quotation",
                fields=["*"],
            )

            batch_size = 500
            for i, quote_data in enumerate(quotations, 1):
                erpnext_id = quote_data.get("name")
                existing = self.db.query(Quotation).filter(Quotation.erpnext_id == erpnext_id).first()

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

                    self.increment_updated()
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

                    self.db.add(quotation)
                    self.increment_created()

                # Batch commit
                if i % batch_size == 0:
                    self.db.commit()
                    logger.debug("quotations_batch_committed", processed=i, total=len(quotations))

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_quotations_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Quotations with its own client."""
        async with httpx.AsyncClient(timeout=120) as client:
            await self.sync_quotations(client, full_sync)

    # ============= ERPNEXT LEAD SYNC =============

    async def sync_erpnext_leads(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync leads from ERPNext CRM."""
        self.start_sync("erpnext_leads", "full" if full_sync else "incremental")

        try:
            leads = await self._fetch_all_doctype(
                client,
                "Lead",
                fields=["*"],
            )

            batch_size = 500
            for i, lead_data in enumerate(leads, 1):
                erpnext_id = lead_data.get("name")
                existing = self.db.query(ERPNextLead).filter(ERPNextLead.erpnext_id == erpnext_id).first()

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
                    self.increment_updated()
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
                    self.db.add(lead)
                    self.increment_created()

                # Batch commit
                if i % batch_size == 0:
                    self.db.commit()
                    logger.debug("erpnext_leads_batch_committed", processed=i, total=len(leads))

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_erpnext_leads_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs ERPNext Leads with its own client."""
        async with httpx.AsyncClient(timeout=120) as client:
            await self.sync_erpnext_leads(client, full_sync)

    # ============= ITEM SYNC =============

    async def sync_items(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync items (products/services) from ERPNext."""
        self.start_sync("items", "full" if full_sync else "incremental")

        try:
            items = await self._fetch_all_doctype(
                client,
                "Item",
                fields=["*"],
            )

            batch_size = 500
            for i, item_data in enumerate(items, 1):
                erpnext_id = item_data.get("name")
                existing = self.db.query(Item).filter(Item.erpnext_id == erpnext_id).first()

                if existing:
                    existing.item_code = item_data.get("item_code", erpnext_id)
                    existing.item_name = item_data.get("item_name", "")
                    existing.item_group = item_data.get("item_group")
                    existing.description = item_data.get("description")
                    existing.is_stock_item = item_data.get("is_stock_item", 1) == 1
                    existing.is_fixed_asset = item_data.get("is_fixed_asset", 0) == 1
                    existing.is_sales_item = item_data.get("is_sales_item", 1) == 1
                    existing.is_purchase_item = item_data.get("is_purchase_item", 1) == 1
                    existing.stock_uom = item_data.get("stock_uom")
                    existing.default_warehouse = item_data.get("default_warehouse")
                    existing.standard_rate = Decimal(str(item_data.get("standard_rate", 0) or 0))
                    existing.valuation_rate = Decimal(str(item_data.get("valuation_rate", 0) or 0))
                    existing.disabled = item_data.get("disabled", 0) == 1
                    existing.has_variants = item_data.get("has_variants", 0) == 1
                    existing.variant_of = item_data.get("variant_of")
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    item = Item(
                        erpnext_id=erpnext_id,
                        item_code=item_data.get("item_code", erpnext_id),
                        item_name=item_data.get("item_name", ""),
                        item_group=item_data.get("item_group"),
                        description=item_data.get("description"),
                        is_stock_item=item_data.get("is_stock_item", 1) == 1,
                        is_fixed_asset=item_data.get("is_fixed_asset", 0) == 1,
                        is_sales_item=item_data.get("is_sales_item", 1) == 1,
                        is_purchase_item=item_data.get("is_purchase_item", 1) == 1,
                        stock_uom=item_data.get("stock_uom"),
                        default_warehouse=item_data.get("default_warehouse"),
                        standard_rate=Decimal(str(item_data.get("standard_rate", 0) or 0)),
                        valuation_rate=Decimal(str(item_data.get("valuation_rate", 0) or 0)),
                        disabled=item_data.get("disabled", 0) == 1,
                        has_variants=item_data.get("has_variants", 0) == 1,
                        variant_of=item_data.get("variant_of"),
                    )
                    self.db.add(item)
                    self.increment_created()

                # Batch commit
                if i % batch_size == 0:
                    self.db.commit()
                    logger.debug("items_batch_committed", processed=i, total=len(items))

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_items_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Items with its own client."""
        async with httpx.AsyncClient(timeout=120) as client:
            await self.sync_items(client, full_sync)

    # ============= CUSTOMER GROUP SYNC =============

    async def sync_customer_groups(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync customer groups from ERPNext."""
        self.start_sync("customer_groups", "full" if full_sync else "incremental")

        try:
            groups = await self._fetch_all_doctype(
                client,
                "Customer Group",
                fields=["*"],
            )

            for group_data in groups:
                erpnext_id = group_data.get("name")
                existing = self.db.query(CustomerGroup).filter(CustomerGroup.erpnext_id == erpnext_id).first()

                if existing:
                    existing.customer_group_name = group_data.get("customer_group_name", erpnext_id)
                    existing.parent_customer_group = group_data.get("parent_customer_group")
                    existing.is_group = group_data.get("is_group", 0) == 1
                    existing.default_price_list = group_data.get("default_price_list")
                    existing.default_payment_terms_template = group_data.get("default_payment_terms_template")
                    existing.lft = group_data.get("lft")
                    existing.rgt = group_data.get("rgt")
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    customer_group = CustomerGroup(
                        erpnext_id=erpnext_id,
                        customer_group_name=group_data.get("customer_group_name", erpnext_id),
                        parent_customer_group=group_data.get("parent_customer_group"),
                        is_group=group_data.get("is_group", 0) == 1,
                        default_price_list=group_data.get("default_price_list"),
                        default_payment_terms_template=group_data.get("default_payment_terms_template"),
                        lft=group_data.get("lft"),
                        rgt=group_data.get("rgt"),
                    )
                    self.db.add(customer_group)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_customer_groups_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Customer Groups with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_customer_groups(client, full_sync)

    # ============= TERRITORY SYNC =============

    async def sync_territories(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync territories from ERPNext."""
        self.start_sync("territories", "full" if full_sync else "incremental")

        try:
            territories = await self._fetch_all_doctype(
                client,
                "Territory",
                fields=["*"],
            )

            for terr_data in territories:
                erpnext_id = terr_data.get("name")
                existing = self.db.query(Territory).filter(Territory.erpnext_id == erpnext_id).first()

                if existing:
                    existing.territory_name = terr_data.get("territory_name", erpnext_id)
                    existing.parent_territory = terr_data.get("parent_territory")
                    existing.is_group = terr_data.get("is_group", 0) == 1
                    existing.territory_manager = terr_data.get("territory_manager")
                    existing.lft = terr_data.get("lft")
                    existing.rgt = terr_data.get("rgt")
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    territory = Territory(
                        erpnext_id=erpnext_id,
                        territory_name=terr_data.get("territory_name", erpnext_id),
                        parent_territory=terr_data.get("parent_territory"),
                        is_group=terr_data.get("is_group", 0) == 1,
                        territory_manager=terr_data.get("territory_manager"),
                        lft=terr_data.get("lft"),
                        rgt=terr_data.get("rgt"),
                    )
                    self.db.add(territory)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_territories_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Territories with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_territories(client, full_sync)

    # ============= SALES PERSON SYNC =============

    async def sync_sales_persons(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync sales persons from ERPNext."""
        self.start_sync("sales_persons", "full" if full_sync else "incremental")

        try:
            persons = await self._fetch_all_doctype(
                client,
                "Sales Person",
                fields=["*"],
            )

            for person_data in persons:
                erpnext_id = person_data.get("name")
                existing = self.db.query(SalesPerson).filter(SalesPerson.erpnext_id == erpnext_id).first()

                if existing:
                    existing.sales_person_name = person_data.get("sales_person_name", erpnext_id)
                    existing.parent_sales_person = person_data.get("parent_sales_person")
                    existing.is_group = person_data.get("is_group", 0) == 1
                    existing.employee = person_data.get("employee")
                    existing.department = person_data.get("department")
                    existing.enabled = person_data.get("enabled", 1) == 1
                    existing.commission_rate = Decimal(str(person_data.get("commission_rate", 0) or 0))
                    existing.lft = person_data.get("lft")
                    existing.rgt = person_data.get("rgt")
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    sales_person = SalesPerson(
                        erpnext_id=erpnext_id,
                        sales_person_name=person_data.get("sales_person_name", erpnext_id),
                        parent_sales_person=person_data.get("parent_sales_person"),
                        is_group=person_data.get("is_group", 0) == 1,
                        employee=person_data.get("employee"),
                        department=person_data.get("department"),
                        enabled=person_data.get("enabled", 1) == 1,
                        commission_rate=Decimal(str(person_data.get("commission_rate", 0) or 0)),
                        lft=person_data.get("lft"),
                        rgt=person_data.get("rgt"),
                    )
                    self.db.add(sales_person)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_sales_persons_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Sales Persons with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_sales_persons(client, full_sync)

    # ============= ITEM GROUP SYNC =============

    async def sync_item_groups(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync item groups from ERPNext."""
        self.start_sync("item_groups", "full" if full_sync else "incremental")

        try:
            groups = await self._fetch_all_doctype(
                client,
                "Item Group",
                fields=["*"],
            )

            for group_data in groups:
                erpnext_id = group_data.get("name")
                existing = self.db.query(ItemGroup).filter(ItemGroup.erpnext_id == erpnext_id).first()

                if existing:
                    existing.item_group_name = group_data.get("item_group_name", erpnext_id)
                    existing.parent_item_group = group_data.get("parent_item_group")
                    existing.is_group = group_data.get("is_group", 0) == 1
                    existing.lft = group_data.get("lft")
                    existing.rgt = group_data.get("rgt")
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    item_group = ItemGroup(
                        erpnext_id=erpnext_id,
                        item_group_name=group_data.get("item_group_name", erpnext_id),
                        parent_item_group=group_data.get("parent_item_group"),
                        is_group=group_data.get("is_group", 0) == 1,
                        lft=group_data.get("lft"),
                        rgt=group_data.get("rgt"),
                    )
                    self.db.add(item_group)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_item_groups_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Item Groups with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_item_groups(client, full_sync)

    # ============= SALES SYNC (COMBINED) =============

    async def sync_sales_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs all sales-related data."""
        async with httpx.AsyncClient(timeout=180) as client:
            # Sync reference data first
            await self.sync_customer_groups(client, full_sync)
            await self.sync_territories(client, full_sync)
            await self.sync_sales_persons(client, full_sync)
            await self.sync_item_groups(client, full_sync)
            await self.sync_items(client, full_sync)
            # Then sync transactional data
            await self.sync_erpnext_leads(client, full_sync)
            await self.sync_quotations(client, full_sync)
            await self.sync_sales_orders(client, full_sync)

    # ============= HR SYNC FUNCTIONS =============

    async def sync_departments(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync departments from ERPNext HR module."""
        self.start_sync("erpnext_departments", full_sync)

        try:
            departments = await self._fetch_all_doctype(
                client,
                "Department",
                fields=["*"],
            )

            for dept_data in departments:
                erpnext_id = dept_data.get("name")
                existing = self.db.query(Department).filter(Department.erpnext_id == erpnext_id).first()

                if existing:
                    existing.department_name = dept_data.get("department_name", erpnext_id)
                    existing.parent_department = dept_data.get("parent_department")
                    existing.company = dept_data.get("company")
                    existing.is_group = dept_data.get("is_group", 0) == 1
                    existing.lft = dept_data.get("lft")
                    existing.rgt = dept_data.get("rgt")
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    department = Department(
                        erpnext_id=erpnext_id,
                        department_name=dept_data.get("department_name", erpnext_id),
                        parent_department=dept_data.get("parent_department"),
                        company=dept_data.get("company"),
                        is_group=dept_data.get("is_group", 0) == 1,
                        lft=dept_data.get("lft"),
                        rgt=dept_data.get("rgt"),
                    )
                    self.db.add(department)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_departments_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Departments with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_departments(client, full_sync)

    async def sync_designations(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync job designations from ERPNext."""
        self.start_sync("erpnext_designations", full_sync)

        try:
            designations = await self._fetch_all_doctype(
                client,
                "Designation",
                fields=["*"],
            )

            for desig_data in designations:
                erpnext_id = desig_data.get("name")
                existing = self.db.query(Designation).filter(Designation.erpnext_id == erpnext_id).first()

                if existing:
                    existing.designation_name = desig_data.get("designation_name", erpnext_id)
                    existing.description = desig_data.get("description")
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    designation = Designation(
                        erpnext_id=erpnext_id,
                        designation_name=desig_data.get("designation_name", erpnext_id),
                        description=desig_data.get("description"),
                    )
                    self.db.add(designation)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_designations_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Designations with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_designations(client, full_sync)

    async def sync_erpnext_users(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync ERPNext system users."""
        self.start_sync("erpnext_users", full_sync)

        try:
            users = await self._fetch_all_doctype(
                client,
                "User",
                fields=["name", "email", "full_name", "first_name", "last_name", "enabled", "user_type"],
            )

            for user_data in users:
                email = user_data.get("email") or user_data.get("name")
                if not email:
                    continue

                existing = self.db.query(ERPNextUser).filter(ERPNextUser.email == email).first()

                # Try to find linked employee by email
                employee_id = None
                employee = self.db.query(Employee).filter(Employee.email == email).first()
                if employee:
                    employee_id = employee.id

                if existing:
                    existing.erpnext_id = user_data.get("name")
                    existing.full_name = user_data.get("full_name")
                    existing.first_name = user_data.get("first_name")
                    existing.last_name = user_data.get("last_name")
                    existing.enabled = user_data.get("enabled", 1) == 1
                    existing.user_type = user_data.get("user_type")
                    existing.employee_id = employee_id
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    erpnext_user = ERPNextUser(
                        erpnext_id=user_data.get("name"),
                        email=email,
                        full_name=user_data.get("full_name"),
                        first_name=user_data.get("first_name"),
                        last_name=user_data.get("last_name"),
                        enabled=user_data.get("enabled", 1) == 1,
                        user_type=user_data.get("user_type"),
                        employee_id=employee_id,
                    )
                    self.db.add(erpnext_user)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_erpnext_users_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs ERPNext Users with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_erpnext_users(client, full_sync)

    async def sync_hd_teams(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync helpdesk teams and their members from ERPNext."""
        self.start_sync("erpnext_hd_teams", full_sync)

        try:
            # Fetch all HD Teams
            teams = await self._fetch_all_doctype(
                client,
                "HD Team",
                fields=["*"],
            )

            for team_data in teams:
                erpnext_id = team_data.get("name")
                existing = self.db.query(HDTeam).filter(HDTeam.erpnext_id == erpnext_id).first()

                if existing:
                    existing.team_name = team_data.get("team_name", erpnext_id)
                    existing.description = team_data.get("description")
                    existing.assignment_rule = team_data.get("assignment_rule")
                    existing.ignore_restrictions = team_data.get("ignore_restrictions", 0) == 1
                    existing.last_synced_at = datetime.utcnow()
                    team = existing
                    self.increment_updated()
                else:
                    team = HDTeam(
                        erpnext_id=erpnext_id,
                        team_name=team_data.get("team_name", erpnext_id),
                        description=team_data.get("description"),
                        assignment_rule=team_data.get("assignment_rule"),
                        ignore_restrictions=team_data.get("ignore_restrictions", 0) == 1,
                    )
                    self.db.add(team)
                    self.db.flush()  # Get the team ID
                    self.increment_created()

                # Sync team members - fetch from HD Team document
                try:
                    team_doc = await self._fetch_document(client, "HD Team", erpnext_id)
                    members_data = team_doc.get("users", [])

                    # Clear existing members for this team
                    self.db.query(HDTeamMember).filter(HDTeamMember.team_id == team.id).delete()

                    for member_data in members_data:
                        user_email = member_data.get("user")
                        if not user_email:
                            continue

                        # Try to find linked employee by email
                        employee_id = None
                        employee = self.db.query(Employee).filter(Employee.email == user_email).first()
                        if employee:
                            employee_id = employee.id

                        member = HDTeamMember(
                            team_id=team.id,
                            user=user_email,
                            user_name=member_data.get("user_name"),
                            employee_id=employee_id,
                        )
                        self.db.add(member)
                except Exception as e:
                    logger.warning(f"Could not fetch members for HD Team {erpnext_id}: {e}")

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_hd_teams_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs HD Teams with its own client."""
        async with httpx.AsyncClient(timeout=120) as client:
            await self.sync_hd_teams(client, full_sync)

    def resolve_employee_relationships(self):
        """Resolve FK relationships for employees based on text field values."""
        # Build lookup maps
        # Department: Employee.department is ERPNext ID like "Sales (call center) - DT"
        # which matches Department.erpnext_id
        dept_map = {
            d.erpnext_id: d.id
            for d in self.db.query(Department).filter(Department.erpnext_id.isnot(None)).all()
        }
        desig_map = {
            d.designation_name: d.id
            for d in self.db.query(Designation).all()
        }
        emp_map = {
            e.erpnext_id: e.id
            for e in self.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).all()
        }

        updated = 0
        for emp in self.db.query(Employee).all():
            changed = False

            # Resolve department (Employee.department is the ERPNext ID)
            if emp.department and emp.department in dept_map:
                if emp.department_id != dept_map[emp.department]:
                    emp.department_id = dept_map[emp.department]
                    changed = True

            # Resolve designation
            if emp.designation and emp.designation in desig_map:
                if emp.designation_id != desig_map[emp.designation]:
                    emp.designation_id = desig_map[emp.designation]
                    changed = True

            # Resolve reports_to (manager)
            if emp.reports_to and emp.reports_to in emp_map:
                if emp.reports_to_id != emp_map[emp.reports_to]:
                    emp.reports_to_id = emp_map[emp.reports_to]
                    changed = True

            if changed:
                updated += 1

        self.db.commit()
        logger.info(f"Resolved {updated} employee relationships")
        return updated

    def resolve_sales_person_employees(self):
        """Resolve FK relationships for sales persons to employees."""
        # Build employee lookup by erpnext_id
        emp_map = {
            e.erpnext_id: e.id
            for e in self.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).all()
        }

        updated = 0
        for sp in self.db.query(SalesPerson).all():
            # The 'employee' field contains the ERPNext Employee ID
            if sp.employee and sp.employee in emp_map:
                if sp.employee_id != emp_map[sp.employee]:
                    sp.employee_id = emp_map[sp.employee]
                    updated += 1

        self.db.commit()
        logger.info(f"Linked {updated} sales persons to employees")
        return updated

    async def sync_hr_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs all HR-related data."""
        async with httpx.AsyncClient(timeout=180) as client:
            # Sync reference data first
            await self.sync_departments(client, full_sync)
            await self.sync_designations(client, full_sync)
            # Then sync users and teams (which link to employees)
            await self.sync_erpnext_users(client, full_sync)
            await self.sync_hd_teams(client, full_sync)
            # Resolve employee FK relationships
            self.resolve_employee_relationships()
            # Link sales persons to employees
            self.resolve_sales_person_employees()
