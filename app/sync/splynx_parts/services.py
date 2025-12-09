from datetime import datetime
import structlog
import httpx

from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from app.models.customer import Customer
from app.models.tariff import Tariff
from app.models.router import Router

logger = structlog.get_logger()


async def sync_services(sync_client, client: httpx.AsyncClient, full_sync: bool):
    """Sync internet services/subscriptions from Splynx.

    Uses bulk endpoint /admin/customers/customer/0/internet-services which returns
    all services across all customers in a single request.
    Links subscriptions to customers, routers, and tariffs for complete relationship mapping.
    """
    sync_client.start_sync("services", "full" if full_sync else "incremental")

    try:
        # Pre-fetch lookup maps for FK resolution
        tariffs_by_splynx_id = {
            t.splynx_id: t.id
            for t in sync_client.db.query(Tariff).filter(Tariff.splynx_id.isnot(None)).all()
        }
        routers_by_splynx_id = {
            r.splynx_id: r.id
            for r in sync_client.db.query(Router).filter(Router.splynx_id.isnot(None)).all()
        }
        customers_by_splynx_id = {
            c.splynx_id: c.id
            for c in sync_client.db.query(Customer).filter(Customer.splynx_id.isnot(None)).all()
        }

        # Fetch all services using bulk endpoint (customer_id=0 means all)
        base_url = sync_client.base_url.rstrip("/")
        services = await sync_client._fetch_paginated(
            client, "/admin/customers/customer/0/internet-services"
        )
        logger.info("splynx_services_fetched", count=len(services))

        for svc_data in services:
            try:
                splynx_id = svc_data.get("id")
                splynx_customer_id = svc_data.get("customer_id")

                # Skip if customer not in our database
                customer_id = customers_by_splynx_id.get(splynx_customer_id)
                if not customer_id:
                    continue

                existing = sync_client.db.query(Subscription).filter(
                    Subscription.splynx_id == splynx_id
                ).first()

                # Map status
                splynx_status = str(svc_data.get("status", "active")).lower()
                status_map = {
                    "active": SubscriptionStatus.ACTIVE,
                    "disabled": SubscriptionStatus.CANCELLED,
                    "blocked": SubscriptionStatus.SUSPENDED,
                    "pending": SubscriptionStatus.PENDING,
                }
                status = status_map.get(splynx_status, SubscriptionStatus.ACTIVE)

                # Get price from unit_price
                price = float(svc_data.get("unit_price", 0) or 0)

                # Resolve router FK
                splynx_router_id = svc_data.get("router_id")
                router_id = routers_by_splynx_id.get(splynx_router_id) if splynx_router_id else None

                # Resolve tariff FK
                splynx_tariff_id = svc_data.get("tariff_id")
                tariff_id = tariffs_by_splynx_id.get(splynx_tariff_id) if splynx_tariff_id else None

                # Get service description/name
                plan_name = svc_data.get("description") or f"Service {splynx_id}"

                # Extract geo data if available
                geo = svc_data.get("geo") or {}
                geo_address = geo.get("address") if isinstance(geo, dict) else None

                if existing:
                    existing.customer_id = customer_id
                    existing.plan_name = plan_name
                    existing.description = svc_data.get("description")
                    existing.price = price
                    existing.status = status
                    existing.router_id = router_id
                    existing.tariff_id = tariff_id
                    existing.splynx_tariff_id = splynx_tariff_id
                    existing.ipv4_address = svc_data.get("ipv4")
                    existing.ipv6_address = svc_data.get("ipv6")
                    existing.mac_address = svc_data.get("mac")
                    existing.last_synced_at = datetime.utcnow()

                    # Parse dates
                    start_date = svc_data.get("start_date")
                    if start_date and start_date != "0000-00-00":
                        try:
                            existing.start_date = datetime.strptime(start_date, "%Y-%m-%d")
                        except (ValueError, TypeError):
                            pass

                    end_date = svc_data.get("end_date")
                    if end_date and end_date != "0000-00-00":
                        try:
                            existing.end_date = datetime.strptime(end_date, "%Y-%m-%d")
                        except (ValueError, TypeError):
                            pass

                    sync_client.increment_updated()
                else:
                    subscription = Subscription(
                        splynx_id=splynx_id,
                        customer_id=customer_id,
                        plan_name=plan_name,
                        description=svc_data.get("description"),
                        price=price,
                        status=status,
                        service_type=SubscriptionType.INTERNET,
                        router_id=router_id,
                        tariff_id=tariff_id,
                        splynx_tariff_id=splynx_tariff_id,
                        ipv4_address=svc_data.get("ipv4"),
                        ipv6_address=svc_data.get("ipv6"),
                        mac_address=svc_data.get("mac"),
                    )

                    # Parse dates
                    start_date = svc_data.get("start_date")
                    if start_date and start_date != "0000-00-00":
                        try:
                            subscription.start_date = datetime.strptime(start_date, "%Y-%m-%d")
                        except (ValueError, TypeError):
                            pass

                    end_date = svc_data.get("end_date")
                    if end_date and end_date != "0000-00-00":
                        try:
                            subscription.end_date = datetime.strptime(end_date, "%Y-%m-%d")
                        except (ValueError, TypeError):
                            pass

                    sync_client.db.add(subscription)
                    sync_client.increment_created()

            except Exception as e:
                logger.warning(
                    "splynx_service_sync_error",
                    service_id=svc_data.get("id"),
                    error=str(e)
                )
                continue

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_services_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
