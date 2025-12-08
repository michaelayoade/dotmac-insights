import httpx
import hashlib
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
import structlog
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.sync.base import BaseSyncClient
from app.models.sync_log import SyncSource, SyncStatus
from app.models.customer import Customer, CustomerStatus, CustomerType
from app.models.pop import Pop
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus, InvoiceSource
from app.models.payment import Payment, PaymentStatus, PaymentMethod, PaymentSource

logger = structlog.get_logger()


class SplynxSync(BaseSyncClient):
    """Sync client for Splynx ISP billing system."""

    source = SyncSource.SPLYNX

    def __init__(self, db: Session):
        super().__init__(db)
        self.base_url = settings.splynx_api_url.rstrip("/")
        self.api_key = settings.splynx_api_key
        self.api_secret = settings.splynx_api_secret
        self.access_token: Optional[str] = None
        self.token_expires: Optional[float] = None

    def _generate_signature(self, nonce: str) -> str:
        """Generate HMAC signature for Splynx API authentication."""
        message = f"{nonce}{self.api_key}"
        signature = hashlib.sha256(
            (message + self.api_secret).encode()
        ).hexdigest()
        return signature

    async def _get_access_token(self, client: httpx.AsyncClient) -> str:
        """Get or refresh access token."""
        if self.access_token and self.token_expires and time.time() < self.token_expires:
            return self.access_token

        nonce = str(int(time.time() * 1000))
        signature = self._generate_signature(nonce)

        response = await client.post(
            f"{self.base_url}/admin/auth/tokens",
            json={
                "auth_type": "api_key",
                "key": self.api_key,
                "signature": signature,
                "nonce": nonce,
            },
        )
        response.raise_for_status()
        data = response.json()

        self.access_token = data.get("access_token")
        # Token typically expires in 1 hour, refresh 5 min early
        self.token_expires = time.time() + 3300

        return self.access_token

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        endpoint: str,
        params: Dict = None,
        json: Dict = None,
    ) -> Any:
        """Make authenticated request to Splynx API."""
        token = await self._get_access_token(client)
        headers = {"Authorization": f"Splynx-EA (access_token={token})"}

        response = await client.request(
            method,
            f"{self.base_url}{endpoint}",
            headers=headers,
            params=params,
            json=json,
        )
        response.raise_for_status()
        return response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_paginated(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        params: Dict = None,
    ) -> List[Dict]:
        """Fetch all records with pagination."""
        all_records = []
        page = 0
        per_page = 100

        while True:
            request_params = {"page": page, "per_page": per_page, **(params or {})}
            data = await self._request(client, "GET", endpoint, params=request_params)

            if not data:
                break

            all_records.extend(data)
            self.increment_fetched(len(data))

            if len(data) < per_page:
                break

            page += 1

        return all_records

    async def test_connection(self) -> bool:
        """Test if Splynx API connection is working."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await self._get_access_token(client)
                # Try to fetch a small amount of data
                await self._request(client, "GET", "/admin/customers/customer", params={"per_page": 1})
            return True
        except Exception as e:
            logger.error("splynx_connection_test_failed", error=str(e))
            return False

    async def sync_all(self, full_sync: bool = False):
        """Sync all entities from Splynx."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self.sync_locations(client, full_sync)
            await self.sync_customers(client, full_sync)
            await self.sync_services(client, full_sync)
            await self.sync_invoices(client, full_sync)
            await self.sync_payments(client, full_sync)

    async def sync_locations(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync POPs/locations from Splynx."""
        self.start_sync("locations", "full" if full_sync else "incremental")

        try:
            # Splynx calls these "locations" or may have custom field
            # Adjust endpoint based on your Splynx configuration
            locations = await self._fetch_paginated(client, "/admin/networking/routers")

            for loc_data in locations:
                splynx_id = loc_data.get("id")
                existing = self.db.query(Pop).filter(Pop.splynx_id == splynx_id).first()

                if existing:
                    existing.name = loc_data.get("title", loc_data.get("name", "Unknown"))
                    existing.address = loc_data.get("address")
                    existing.last_synced_at = datetime.utcnow()
                    self.increment_updated()
                else:
                    pop = Pop(
                        splynx_id=splynx_id,
                        name=loc_data.get("title", loc_data.get("name", "Unknown")),
                        address=loc_data.get("address"),
                    )
                    self.db.add(pop)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_customers(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync customers from Splynx."""
        self.start_sync("customers", "full" if full_sync else "incremental")

        try:
            customers = await self._fetch_paginated(client, "/admin/customers/customer")

            for cust_data in customers:
                splynx_id = cust_data.get("id")
                existing = self.db.query(Customer).filter(Customer.splynx_id == splynx_id).first()

                # Map Splynx status to our status
                splynx_status = cust_data.get("status", "active").lower()
                status_map = {
                    "active": CustomerStatus.ACTIVE,
                    "inactive": CustomerStatus.INACTIVE,
                    "blocked": CustomerStatus.SUSPENDED,
                    "disabled": CustomerStatus.CANCELLED,
                }
                status = status_map.get(splynx_status, CustomerStatus.ACTIVE)

                # Find POP if location_id exists
                pop_id = None
                if cust_data.get("location_id"):
                    pop = self.db.query(Pop).filter(Pop.splynx_id == cust_data["location_id"]).first()
                    if pop:
                        pop_id = pop.id

                customer_type = CustomerType.RESIDENTIAL
                if cust_data.get("category") in ["business", "corporate", "enterprise"]:
                    customer_type = CustomerType.BUSINESS

                if existing:
                    existing.name = cust_data.get("name", "")
                    existing.email = cust_data.get("email")
                    existing.phone = cust_data.get("phone")
                    existing.address = cust_data.get("street_1")
                    existing.city = cust_data.get("city")
                    existing.status = status
                    existing.customer_type = customer_type
                    existing.pop_id = pop_id
                    existing.account_number = cust_data.get("login")
                    existing.last_synced_at = datetime.utcnow()

                    # Parse dates
                    if cust_data.get("date_add"):
                        try:
                            existing.signup_date = datetime.fromisoformat(
                                cust_data["date_add"].replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    self.increment_updated()
                else:
                    customer = Customer(
                        splynx_id=splynx_id,
                        name=cust_data.get("name", ""),
                        email=cust_data.get("email"),
                        phone=cust_data.get("phone"),
                        address=cust_data.get("street_1"),
                        city=cust_data.get("city"),
                        status=status,
                        customer_type=customer_type,
                        pop_id=pop_id,
                        account_number=cust_data.get("login"),
                    )

                    if cust_data.get("date_add"):
                        try:
                            customer.signup_date = datetime.fromisoformat(
                                cust_data["date_add"].replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    self.db.add(customer)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_services(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync internet services/subscriptions from Splynx."""
        self.start_sync("services", "full" if full_sync else "incremental")

        try:
            services = await self._fetch_paginated(client, "/admin/customers/customer-internet-services")

            for svc_data in services:
                splynx_id = svc_data.get("id")
                existing = self.db.query(Subscription).filter(Subscription.splynx_id == splynx_id).first()

                # Find customer
                customer_splynx_id = svc_data.get("customer_id")
                customer = self.db.query(Customer).filter(Customer.splynx_id == customer_splynx_id).first()

                if not customer:
                    logger.warning("service_customer_not_found", splynx_customer_id=customer_splynx_id)
                    self.increment_failed()
                    continue

                # Map status
                splynx_status = svc_data.get("status", "active").lower()
                status_map = {
                    "active": SubscriptionStatus.ACTIVE,
                    "disabled": SubscriptionStatus.CANCELLED,
                    "blocked": SubscriptionStatus.SUSPENDED,
                    "pending": SubscriptionStatus.PENDING,
                }
                status = status_map.get(splynx_status, SubscriptionStatus.ACTIVE)

                price = float(svc_data.get("price", 0) or 0)

                if existing:
                    existing.customer_id = customer.id
                    existing.plan_name = svc_data.get("tariff_name", svc_data.get("description", "Unknown"))
                    existing.price = price
                    existing.status = status
                    existing.download_speed = svc_data.get("download_speed")
                    existing.upload_speed = svc_data.get("upload_speed")
                    existing.last_synced_at = datetime.utcnow()

                    if svc_data.get("start_date"):
                        try:
                            existing.start_date = datetime.fromisoformat(
                                svc_data["start_date"].replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    self.increment_updated()
                else:
                    subscription = Subscription(
                        splynx_id=splynx_id,
                        customer_id=customer.id,
                        plan_name=svc_data.get("tariff_name", svc_data.get("description", "Unknown")),
                        price=price,
                        status=status,
                        download_speed=svc_data.get("download_speed"),
                        upload_speed=svc_data.get("upload_speed"),
                    )

                    if svc_data.get("start_date"):
                        try:
                            subscription.start_date = datetime.fromisoformat(
                                svc_data["start_date"].replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    self.db.add(subscription)
                    self.increment_created()

            self.db.commit()
            self.complete_sync()

        except Exception as e:
            self.db.rollback()
            self.fail_sync(str(e))
            raise

    async def sync_invoices(self, client: httpx.AsyncClient, full_sync: bool = False):
        """Sync invoices from Splynx."""
        self.start_sync("invoices", "full" if full_sync else "incremental")

        try:
            invoices = await self._fetch_paginated(client, "/admin/finance/invoices")

            for inv_data in invoices:
                splynx_id = inv_data.get("id")
                existing = self.db.query(Invoice).filter(
                    Invoice.splynx_id == splynx_id,
                    Invoice.source == InvoiceSource.SPLYNX,
                ).first()

                # Find customer
                customer_splynx_id = inv_data.get("customer_id")
                customer = self.db.query(Customer).filter(Customer.splynx_id == customer_splynx_id).first()

                customer_id = customer.id if customer else None

                # Map status
                splynx_status = inv_data.get("status", "").lower()
                status_map = {
                    "paid": InvoiceStatus.PAID,
                    "unpaid": InvoiceStatus.PENDING,
                    "overdue": InvoiceStatus.OVERDUE,
                    "partially_paid": InvoiceStatus.PARTIALLY_PAID,
                    "cancelled": InvoiceStatus.CANCELLED,
                }
                status = status_map.get(splynx_status, InvoiceStatus.PENDING)

                total_amount = float(inv_data.get("total", 0) or 0)
                amount_paid = float(inv_data.get("payment_amount", 0) or 0)

                if existing:
                    existing.customer_id = customer_id
                    existing.invoice_number = inv_data.get("number")
                    existing.total_amount = total_amount
                    existing.amount = total_amount
                    existing.amount_paid = amount_paid
                    existing.balance = total_amount - amount_paid
                    existing.status = status
                    existing.last_synced_at = datetime.utcnow()

                    if inv_data.get("date_created"):
                        try:
                            existing.invoice_date = datetime.fromisoformat(
                                inv_data["date_created"].replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    if inv_data.get("date_due"):
                        try:
                            existing.due_date = datetime.fromisoformat(
                                inv_data["date_due"].replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    self.increment_updated()
                else:
                    invoice = Invoice(
                        splynx_id=splynx_id,
                        source=InvoiceSource.SPLYNX,
                        customer_id=customer_id,
                        invoice_number=inv_data.get("number"),
                        total_amount=total_amount,
                        amount=total_amount,
                        amount_paid=amount_paid,
                        balance=total_amount - amount_paid,
                        status=status,
                        invoice_date=datetime.utcnow(),  # Default, will be overwritten
                    )

                    if inv_data.get("date_created"):
                        try:
                            invoice.invoice_date = datetime.fromisoformat(
                                inv_data["date_created"].replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    if inv_data.get("date_due"):
                        try:
                            invoice.due_date = datetime.fromisoformat(
                                inv_data["date_due"].replace("Z", "+00:00")
                            )
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
        """Sync payments from Splynx."""
        self.start_sync("payments", "full" if full_sync else "incremental")

        try:
            payments = await self._fetch_paginated(client, "/admin/finance/payments")

            for pay_data in payments:
                splynx_id = pay_data.get("id")
                existing = self.db.query(Payment).filter(
                    Payment.splynx_id == splynx_id,
                    Payment.source == PaymentSource.SPLYNX,
                ).first()

                # Find customer
                customer_splynx_id = pay_data.get("customer_id")
                customer = self.db.query(Customer).filter(Customer.splynx_id == customer_splynx_id).first()

                customer_id = customer.id if customer else None

                # Find invoice if referenced
                invoice_id = None
                if pay_data.get("invoice_id"):
                    invoice = self.db.query(Invoice).filter(
                        Invoice.splynx_id == pay_data["invoice_id"],
                        Invoice.source == InvoiceSource.SPLYNX,
                    ).first()
                    if invoice:
                        invoice_id = invoice.id

                amount = float(pay_data.get("amount", 0) or 0)

                # Map payment method
                method_str = (pay_data.get("payment_type", "") or "").lower()
                method_map = {
                    "cash": PaymentMethod.CASH,
                    "bank": PaymentMethod.BANK_TRANSFER,
                    "card": PaymentMethod.CARD,
                    "paystack": PaymentMethod.PAYSTACK,
                    "flutterwave": PaymentMethod.FLUTTERWAVE,
                }
                payment_method = method_map.get(method_str, PaymentMethod.OTHER)

                if existing:
                    existing.customer_id = customer_id
                    existing.invoice_id = invoice_id
                    existing.amount = amount
                    existing.payment_method = payment_method
                    existing.receipt_number = pay_data.get("receipt_number")
                    existing.transaction_reference = pay_data.get("transaction_id")
                    existing.last_synced_at = datetime.utcnow()

                    if pay_data.get("date"):
                        try:
                            existing.payment_date = datetime.fromisoformat(
                                pay_data["date"].replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    self.increment_updated()
                else:
                    payment = Payment(
                        splynx_id=splynx_id,
                        source=PaymentSource.SPLYNX,
                        customer_id=customer_id,
                        invoice_id=invoice_id,
                        amount=amount,
                        payment_method=payment_method,
                        receipt_number=pay_data.get("receipt_number"),
                        transaction_reference=pay_data.get("transaction_id"),
                        payment_date=datetime.utcnow(),  # Default
                    )

                    if pay_data.get("date"):
                        try:
                            payment.payment_date = datetime.fromisoformat(
                                pay_data["date"].replace("Z", "+00:00")
                            )
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
