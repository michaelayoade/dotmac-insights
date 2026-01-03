from datetime import datetime, date
import structlog
import httpx

from app.models.customer_usage import CustomerUsage
from app.models.party import PartyExternalId
from app.models.subscription import Subscription

logger = structlog.get_logger()


async def sync_customer_usage(sync_client, client: httpx.AsyncClient, full_sync: bool):
    """Sync customer traffic counters from Splynx.

    Uses bulk endpoint /admin/customers/customer-traffic-counter which returns
    daily bandwidth usage per service across all customers.
    """
    sync_client.start_sync("customer_usage", "full" if full_sync else "incremental")

    try:
        # Map subscriptions by splynx service_id
        subscriptions_by_splynx_id = {
            s.splynx_id: (s.id, s.party_id)
            for s in sync_client.db.query(Subscription).filter(Subscription.splynx_id.isnot(None)).all()
        }

        # Fetch all traffic counters using bulk endpoint
        usage_records = await sync_client._fetch_paginated(
            client, "/admin/customers/customer-traffic-counter"
        )
        logger.info("splynx_usage_fetched", count=len(usage_records))

        batch_size = 500
        processed = 0
        skipped = 0

        for i, usage_data in enumerate(usage_records, 1):
            try:
                splynx_service_id = usage_data.get("service_id")
                date_str = usage_data.get("date")

                if not splynx_service_id or not date_str:
                    skipped += 1
                    continue

                # Parse date
                try:
                    usage_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    skipped += 1
                    continue

                # Skip invalid dates (0000-00-00)
                if usage_date.year < 2000:
                    skipped += 1
                    continue

                # Resolve subscription and party
                sub_info = subscriptions_by_splynx_id.get(splynx_service_id)
                if sub_info:
                    subscription_id, party_id = sub_info
                else:
                    # No subscription found - try to get party_id from record if available
                    party_id = None
                    subscription_id = None
                    splynx_customer_id = usage_data.get("customer_id")
                    if splynx_customer_id:
                        party_ext = (
                            sync_client.db.query(PartyExternalId)
                            .filter(
                                PartyExternalId.system == "splynx",
                                PartyExternalId.external_id == str(splynx_customer_id),
                                PartyExternalId.external_key_type == "customer_id",
                            )
                            .first()
                        )
                        party_id = party_ext.party_id if party_ext else None

                # Skip if we can't link to a party
                if not party_id:
                    skipped += 1
                    continue

                # Check if record exists (unique on service_id + date)
                existing = sync_client.db.query(CustomerUsage).filter(
                    CustomerUsage.splynx_service_id == splynx_service_id,
                    CustomerUsage.usage_date == usage_date
                ).first()

                upload_bytes = int(usage_data.get("up", 0) or 0)
                download_bytes = int(usage_data.get("down", 0) or 0)

                if existing:
                    # Update existing record
                    existing.upload_bytes = upload_bytes
                    existing.download_bytes = download_bytes
                    existing.party_id = party_id
                    existing.subscription_id = subscription_id
                    sync_client.increment_updated()
                else:
                    # Create new record
                    usage_record = CustomerUsage(
                        party_id=party_id,
                        subscription_id=subscription_id,
                        splynx_service_id=splynx_service_id,
                        usage_date=usage_date,
                        upload_bytes=upload_bytes,
                        download_bytes=download_bytes,
                    )
                    sync_client.db.add(usage_record)
                    sync_client.increment_created()

                processed += 1

                # Commit in batches
                if i % batch_size == 0:
                    sync_client.db.commit()
                    logger.debug("usage_batch_committed", processed=i, total=len(usage_records))

            except Exception as e:
                logger.warning("usage_record_error", error=str(e), data=usage_data)
                skipped += 1
                continue

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_usage_sync_complete",
            processed=processed,
            skipped=skipped,
            created=sync_client.records_created,
            updated=sync_client.records_updated,
        )

    except Exception as e:
        logger.error("splynx_usage_sync_error", error=str(e))
        sync_client.fail_sync(str(e))
        raise
