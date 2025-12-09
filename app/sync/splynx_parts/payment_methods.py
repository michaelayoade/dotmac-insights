from datetime import datetime
import structlog
import httpx

from app.models.payment_method import PaymentMethod

logger = structlog.get_logger()


async def sync_payment_methods(sync_client, client: httpx.AsyncClient, full_sync: bool):
    """Sync payment methods from Splynx.

    Syncs payment method definitions including:
    - Method name and localized names
    - Active status
    - Linked bank accounts
    - E-invoicing integration
    """
    sync_client.start_sync("payment_methods", "full" if full_sync else "incremental")

    try:
        # Fetch all payment methods
        methods = await sync_client._fetch_paginated(
            client, "/admin/finance/payment-methods"
        )
        logger.info("splynx_payment_methods_fetched", count=len(methods))

        for method_data in methods:
            try:
                splynx_id = method_data.get("id")
                if not splynx_id:
                    continue

                existing = sync_client.db.query(PaymentMethod).filter(
                    PaymentMethod.splynx_id == splynx_id
                ).first()

                name = method_data.get("name", f"Method {splynx_id}")
                is_active = bool(method_data.get("is_active", True))

                if existing:
                    existing.name = name
                    existing.is_active = is_active
                    existing.name_1 = method_data.get("name_1")
                    existing.name_2 = method_data.get("name_2")
                    existing.name_3 = method_data.get("name_3")
                    existing.name_4 = method_data.get("name_4")
                    existing.name_5 = method_data.get("name_5")
                    existing.accounting_bank_accounts_id = method_data.get(
                        "accounting_bank_accounts_id"
                    )
                    existing.einvoicing_payment_methods_id = method_data.get(
                        "einvoicing_payment_methods_id"
                    )
                    existing.last_synced_at = datetime.utcnow()
                    sync_client.increment_updated()
                else:
                    payment_method = PaymentMethod(
                        splynx_id=splynx_id,
                        name=name,
                        is_active=is_active,
                        name_1=method_data.get("name_1"),
                        name_2=method_data.get("name_2"),
                        name_3=method_data.get("name_3"),
                        name_4=method_data.get("name_4"),
                        name_5=method_data.get("name_5"),
                        accounting_bank_accounts_id=method_data.get(
                            "accounting_bank_accounts_id"
                        ),
                        einvoicing_payment_methods_id=method_data.get(
                            "einvoicing_payment_methods_id"
                        ),
                        last_synced_at=datetime.utcnow(),
                    )
                    sync_client.db.add(payment_method)
                    sync_client.increment_created()

            except Exception as e:
                logger.warning(
                    "splynx_payment_method_sync_error",
                    method_id=method_data.get("id"),
                    error=str(e)
                )
                continue

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_payment_methods_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
