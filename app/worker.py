"""Celery worker configuration and app setup."""
from celery import Celery
from celery.schedules import crontab
import structlog

from app.config import settings

logger = structlog.get_logger()

# Determine broker/backend
if settings.redis_url:
    broker_url = backend_url = settings.redis_url
elif settings.is_production:
    raise ValueError("REDIS_URL must be configured in production for Celery to run")
else:
    broker_url = backend_url = "redis://localhost:6379/0"
    logger.warning("celery_default_redis", message="Using local Redis fallback for Celery in non-production")

# Create Celery app
celery_app = Celery(
    "dotmac_insights",
    broker=broker_url,
    backend=backend_url,
    include=[
        "app.tasks.sync_tasks",
        "app.tasks.performance_tasks",
        "app.tasks.platform_tasks",
        "app.tasks.event_tasks",
        "app.tasks.workflow_tasks",
        "app.tasks.scheduled_actions",
        "app.tasks.provisioning_tasks",
        "app.tasks.bundle_tasks",
        "app.tasks.monitoring_tasks",
        "app.tasks.marketing_tasks",
        "app.tasks.validation_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes max per task (password sync needs time)
    task_soft_time_limit=1740,  # Soft limit at 29 minutes
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
    task_acks_late=True,  # Ack after task completes (for reliability)
    task_reject_on_worker_lost=True,
    result_expires=86400,  # Results expire after 24 hours
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # Incremental sync every 15 minutes (staggered)
    "sync-splynx-customers-incremental": {
        "task": "app.tasks.sync_tasks.sync_splynx_customers",
        "schedule": crontab(minute="*/15"),  # Every 15 mins at :00, :15, :30, :45
        "kwargs": {"full_sync": False},
    },
    "sync-splynx-credit-notes-incremental": {
        "task": "app.tasks.sync_tasks.sync_splynx_credit_notes",
        "schedule": crontab(minute="8,23,38,53"),
        "kwargs": {"full_sync": False},
    },
    "sync-splynx-invoices-incremental": {
        "task": "app.tasks.sync_tasks.sync_splynx_invoices",
        "schedule": crontab(minute="2,17,32,47"),  # Offset by 2 mins
        "kwargs": {"full_sync": False},
    },
    "sync-splynx-services-incremental": {
        "task": "app.tasks.sync_tasks.sync_splynx_services",
        "schedule": crontab(minute="3,18,33,48"),  # Offset by 3 mins
        "kwargs": {"full_sync": False},
    },
    "sync-splynx-payments-incremental": {
        "task": "app.tasks.sync_tasks.sync_splynx_payments",
        "schedule": crontab(minute="4,19,34,49"),  # Offset by 4 mins
        "kwargs": {"full_sync": False},
    },
    # Full sync nightly at 2 AM
    "sync-splynx-full-nightly": {
        "task": "app.tasks.sync_tasks.sync_splynx_all",
        "schedule": crontab(hour=settings.full_sync_hour, minute=0),
        "kwargs": {"full_sync": True},
    },
    # ERPNext incremental (customers/invoices/payments/expenses)
    "sync-erpnext-customers-incremental": {
        "task": "app.tasks.sync_tasks.sync_erpnext_customers",
        "schedule": crontab(minute="7,22,37,52"),
        "kwargs": {"full_sync": False},
    },
    "sync-erpnext-invoices-incremental": {
        "task": "app.tasks.sync_tasks.sync_erpnext_invoices",
        "schedule": crontab(minute="9,24,39,54"),
        "kwargs": {"full_sync": False},
    },
    "sync-erpnext-payments-incremental": {
        "task": "app.tasks.sync_tasks.sync_erpnext_payments",
        "schedule": crontab(minute="11,26,41,56"),
        "kwargs": {"full_sync": False},
    },
    "sync-erpnext-expenses-incremental": {
        "task": "app.tasks.sync_tasks.sync_erpnext_expenses",
        "schedule": crontab(minute="13,28,43,58"),
        "kwargs": {"full_sync": False},
    },
    "sync-erpnext-hd-tickets-incremental": {
        "task": "app.tasks.sync_tasks.sync_erpnext_hd_tickets",
        "schedule": crontab(minute="10,25,40,55"),
        "kwargs": {"full_sync": False},
    },
    # ERPNext accounting incremental (staggered to avoid overwhelming ERPNext)
    "sync-erpnext-accounting-incremental": {
        "task": "app.tasks.sync_tasks.sync_erpnext_accounting",
        "schedule": crontab(minute="14,44"),  # Every 30 mins (accounting is heavier)
        "kwargs": {"full_sync": False},
    },
    "sync-erpnext-extended-accounting-incremental": {
        "task": "app.tasks.sync_tasks.sync_erpnext_extended_accounting",
        "schedule": crontab(minute="16,46"),
        "kwargs": {"full_sync": False},
    },
    # ERPNext sales incremental
    "sync-erpnext-sales-incremental": {
        "task": "app.tasks.sync_tasks.sync_erpnext_sales",
        "schedule": crontab(minute="18,48"),  # Every 30 mins
        "kwargs": {"full_sync": False},
    },
    # ERPNext HR incremental (less frequent - HR data changes infrequently)
    "sync-erpnext-hr-incremental": {
        "task": "app.tasks.sync_tasks.sync_erpnext_hr",
        "schedule": crontab(hour="*/2", minute=20),  # Every 2 hours
        "kwargs": {"full_sync": False},
    },
    # ERPNext inventory items incremental
    "sync-erpnext-items-incremental": {
        "task": "app.tasks.sync_tasks.sync_erpnext_items",
        "schedule": crontab(minute="22,52"),  # Every 30 mins
        "kwargs": {"full_sync": False},
    },
    # ERPNext full nightly
    "sync-erpnext-full-nightly": {
        "task": "app.tasks.sync_tasks.sync_erpnext_all",
        "schedule": crontab(hour=settings.full_sync_hour, minute=10),
        "kwargs": {"full_sync": True},
    },
    # Chatwoot incremental
    "sync-chatwoot-contacts-incremental": {
        "task": "app.tasks.sync_tasks.sync_chatwoot_contacts",
        "schedule": crontab(minute="5,20,35,50"),
        "kwargs": {"full_sync": False},
    },
    "sync-chatwoot-conversations-incremental": {
        "task": "app.tasks.sync_tasks.sync_chatwoot_conversations",
        "schedule": crontab(minute="6,21,36,51"),
        "kwargs": {"full_sync": False},
    },
    # Chatwoot full nightly
    "sync-chatwoot-full-nightly": {
        "task": "app.tasks.sync_tasks.sync_chatwoot_all",
        "schedule": crontab(hour=settings.full_sync_hour, minute=20),
        "kwargs": {"full_sync": True},
    },
    # DLQ processor - runs every 10 minutes to retry failed records
    "process-dlq-records": {
        "task": "app.tasks.sync_tasks.process_dlq_records",
        "schedule": crontab(minute="*/10"),  # Every 10 minutes
        "kwargs": {"limit": 50},
    },
    # Performance module tasks
    "performance-check-scoring-deadlines": {
        "task": "performance.check_scoring_deadlines",
        "schedule": crontab(hour=1, minute=0),  # Daily at 1 AM
    },
    "performance-check-review-deadlines": {
        "task": "performance.check_review_deadlines",
        "schedule": crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    "performance-check-period-closing": {
        "task": "performance.check_period_closing",
        "schedule": crontab(hour=9, minute=0),  # Daily at 9 AM - warn about periods ending soon
    },
    "performance-weekly-summaries": {
        "task": "performance.send_weekly_summaries",
        "schedule": crontab(hour=8, minute=30, day_of_week=1),  # Every Monday at 8:30 AM
    },
    # Platform integration tasks (only effective if platform configured)
    "platform-validate-license": {
        "task": "app.tasks.platform.validate_license",
        "schedule": settings.license_check_interval_seconds,  # Default: hourly
    },
    "platform-refresh-feature-flags": {
        "task": "app.tasks.platform.refresh_feature_flags",
        "schedule": settings.feature_flags_refresh_interval_seconds,  # Default: 5 minutes
    },
    "platform-report-usage": {
        "task": "app.tasks.platform.report_usage",
        "schedule": settings.usage_report_interval_seconds,  # Default: hourly
    },
    "platform-send-heartbeat": {
        "task": "app.tasks.platform.send_heartbeat",
        "schedule": settings.heartbeat_interval_seconds,  # Default: 5 minutes
    },
    # Data Bundle tasks
    "bundles-process-usage": {
        "task": "bundles.process_usage",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "bundles-check-exhaustion": {
        "task": "bundles.check_exhaustion",
        "schedule": crontab(minute="*"),  # Every minute
    },
    "bundles-process-expiry": {
        "task": "bundles.process_expiry",
        "schedule": crontab(hour=0, minute=5),  # Daily at 00:05
    },
    "bundles-send-alerts": {
        "task": "bundles.send_alerts",
        "schedule": crontab(minute=15),  # Every hour at :15
    },
    "bundles-auto-activate": {
        "task": "bundles.auto_activate_pending",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "bundles-cleanup-expired": {
        "task": "bundles.cleanup_expired",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Weekly on Sunday at 3 AM
    },
    # Network Monitoring (SNMP) tasks
    "monitoring-poll-devices": {
        "task": "monitoring.poll_devices",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "monitoring-aggregate-metrics": {
        "task": "monitoring.aggregate_metrics",
        "schedule": crontab(minute=5),  # Hourly at :05
    },
    "monitoring-cleanup-metrics": {
        "task": "monitoring.cleanup_metrics",
        "schedule": crontab(hour=3, minute=30),  # Daily at 3:30 AM
    },
    # Marketing module tasks
    "marketing-process-journey-steps": {
        "task": "app.tasks.marketing_tasks.process_journey_steps",
        "schedule": crontab(minute="*"),
        "kwargs": {"batch_size": 100},
    },
    "marketing-publish-scheduled-posts": {
        "task": "app.tasks.marketing_tasks.publish_scheduled_posts",
        "schedule": crontab(minute="*"),
        "kwargs": {"batch_size": 50},
    },
    "marketing-sync-social-metrics": {
        "task": "app.tasks.marketing_tasks.sync_social_metrics",
        "schedule": crontab(minute="*/15"),
        "kwargs": {"batch_size": 50},
    },
    "marketing-refresh-audiences": {
        "task": "app.tasks.marketing_tasks.refresh_audience_segments",
        "schedule": crontab(hour="*/4", minute=5),
    },
    "marketing-sync-social-tokens": {
        "task": "app.tasks.marketing_tasks.sync_social_account_tokens",
        "schedule": crontab(hour="*/6", minute=10),
        "kwargs": {"batch_size": 25},
    },
    "marketing-sync-email-metrics": {
        "task": "app.tasks.marketing_tasks.sync_email_metrics",
        "schedule": crontab(minute="*/30"),
        "kwargs": {"batch_size": 200},
    },
    "marketing-refresh-integration-tokens": {
        "task": "app.tasks.marketing_tasks.refresh_marketing_integration_tokens",
        "schedule": crontab(hour="*/6", minute=20),
        "kwargs": {"refresh_window_hours": 24},
    },
    "finance-validation-backfill": {
        "task": "app.tasks.validation_tasks.audit_finance_validation",
        "schedule": crontab(hour=2, minute=35),
        "kwargs": {"batch_size": 500},
    },
}
