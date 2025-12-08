import httpx
from datetime import datetime
from typing import Optional, Dict, Any, List
import structlog
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.sync.base import BaseSyncClient
from app.models.sync_log import SyncSource, SyncStatus
from app.models.customer import Customer
from app.models.employee import Employee, EmploymentStatus
from app.models.expense import Expense, ExpenseStatus
from app.models.invoice import Invoice, InvoiceStatus, InvoiceSource
from app.models.payment import Payment, PaymentStatus, PaymentMethod, PaymentSource

logger = structlog.get_logger()


class ERPNextSync(BaseSyncClient):
    """Sync client for ERPNext ERP system."""

    source = SyncSource.ERPNEXT

    def __init__(self, db: Session):
        super().__init__(db)
        self.base_url = settings.erpnext_api_url.rstrip("/")
        self.api_key = settings.erpnext_api_key
        self.api_secret = settings.erpnext_api_secret

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
        params: Dict = None,
        json: Dict = None,
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
        fields: List[str] = None,
        filters: Dict = None,
        limit_start: int = 0,
        limit_page_length: int = 100,
    ) -> List[Dict]:
        """Fetch records of a specific doctype."""
        params = {
            "doctype": doctype,
            "limit_start": limit_start,
            "limit_page_length": limit_page_length,
        }

        if fields:
            params["fields"] = str(fields)

        if filters:
            params["filters"] = str(filters)

        data = await self._request(client, "GET", "/api/resource/" + doctype, params=params)
        return data.get("data", [])

    async def _fetch_all_doctype(
        self,
        client: httpx.AsyncClient,
        doctype: str,
        fields: List[str] = None,
        filters: Dict = None,
    ) -> List[Dict]:
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

    async def sync_customers(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync customers from ERPNext (to match with Splynx customers)."""
        self.start_sync("customers", "full" if full_sync else "incremental")

        try:
            customers = await self._fetch_all_doctype(
                client,
                "Customer",
                fields=["name", "customer_name", "email_id", "mobile_no", "customer_type"],
            )

            for cust_data in customers:
                erpnext_id = cust_data.get("name")

                # Try to match with existing customer by email or name
                existing = self.db.query(Customer).filter(
                    Customer.erpnext_id == erpnext_id
                ).first()

                if not existing:
                    # Try to match by email
                    email = cust_data.get("email_id")
                    if email:
                        existing = self.db.query(Customer).filter(
                            Customer.email == email
                        ).first()

                if existing:
                    existing.erpnext_id = erpnext_id
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    # Create new customer record
                    customer = Customer(
                        erpnext_id=erpnext_id,
                        name=cust_data.get("customer_name", ""),
                        email=cust_data.get("email_id"),
                        phone=cust_data.get("mobile_no"),
                    )
                    self.db.add(customer)
                    self.increment_created()

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
                ],
            )

            for inv_data in invoices:
                erpnext_id = inv_data.get("name")
                existing = self.db.query(Invoice).filter(
                    Invoice.erpnext_id == erpnext_id,
                    Invoice.source == InvoiceSource.ERPNEXT,
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

                if existing:
                    existing.customer_id = customer_id
                    existing.total_amount = total_amount
                    existing.amount = total_amount
                    existing.amount_paid = paid_amount
                    existing.balance = outstanding
                    existing.status = status
                    existing.currency = inv_data.get("currency", "NGN")
                    existing.last_synced_at = datetime.utcnow()

                    if inv_data.get("posting_date"):
                        try:
                            existing.invoice_date = datetime.fromisoformat(inv_data["posting_date"])
                        except (ValueError, TypeError):
                            pass

                    if inv_data.get("due_date"):
                        try:
                            existing.due_date = datetime.fromisoformat(inv_data["due_date"])
                        except (ValueError, TypeError):
                            pass

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

                    if inv_data.get("posting_date"):
                        try:
                            invoice.invoice_date = datetime.fromisoformat(inv_data["posting_date"])
                        except (ValueError, TypeError):
                            pass

                    if inv_data.get("due_date"):
                        try:
                            invoice.due_date = datetime.fromisoformat(inv_data["due_date"])
                        except (ValueError, TypeError):
                            pass

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
                ],
            )

            for pay_data in payments:
                # Only process customer payments
                if pay_data.get("party_type") != "Customer":
                    continue

                erpnext_id = pay_data.get("name")
                existing = self.db.query(Payment).filter(
                    Payment.erpnext_id == erpnext_id,
                    Payment.source == PaymentSource.ERPNEXT,
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

                if existing:
                    existing.customer_id = customer_id
                    existing.amount = amount
                    existing.payment_method = payment_method
                    existing.transaction_reference = pay_data.get("reference_no")
                    existing.last_synced_at = datetime.utcnow()

                    if pay_data.get("posting_date"):
                        try:
                            existing.payment_date = datetime.fromisoformat(pay_data["posting_date"])
                        except (ValueError, TypeError):
                            pass

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

                    if pay_data.get("posting_date"):
                        try:
                            payment.payment_date = datetime.fromisoformat(pay_data["posting_date"])
                        except (ValueError, TypeError):
                            pass

                    self.db.add(payment)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_expenses(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync expenses from ERPNext for cost analysis."""
        self.start_sync("expenses", "full" if full_sync else "incremental")

        try:
            # Fetch from multiple expense-related doctypes
            expenses = await self._fetch_all_doctype(
                client,
                "Expense Claim",
                fields=[
                    "name", "employee", "expense_type", "posting_date",
                    "total_claimed_amount", "status", "cost_center",
                ],
            )

            for exp_data in expenses:
                erpnext_id = exp_data.get("name")
                existing = self.db.query(Expense).filter(Expense.erpnext_id == erpnext_id).first()

                # Map status
                status_str = (exp_data.get("status", "") or "").lower()
                status_map = {
                    "draft": ExpenseStatus.DRAFT,
                    "pending": ExpenseStatus.PENDING,
                    "approved": ExpenseStatus.APPROVED,
                    "paid": ExpenseStatus.PAID,
                    "cancelled": ExpenseStatus.CANCELLED,
                }
                status = status_map.get(status_str, ExpenseStatus.PAID)

                amount = float(exp_data.get("total_claimed_amount", 0) or 0)

                if existing:
                    existing.expense_type = exp_data.get("expense_type")
                    existing.amount = amount
                    existing.status = status
                    existing.cost_center = exp_data.get("cost_center")
                    existing.last_synced_at = datetime.utcnow()

                    if exp_data.get("posting_date"):
                        try:
                            existing.expense_date = datetime.fromisoformat(exp_data["posting_date"])
                        except (ValueError, TypeError):
                            pass

                    self.increment_updated()
                else:
                    expense = Expense(
                        erpnext_id=erpnext_id,
                        expense_type=exp_data.get("expense_type"),
                        amount=amount,
                        status=status,
                        cost_center=exp_data.get("cost_center"),
                        expense_date=datetime.utcnow(),
                    )

                    if exp_data.get("posting_date"):
                        try:
                            expense.expense_date = datetime.fromisoformat(exp_data["posting_date"])
                        except (ValueError, TypeError):
                            pass

                    self.db.add(expense)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise
