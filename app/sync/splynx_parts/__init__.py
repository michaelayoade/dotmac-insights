"""Helpers for Splynx sync broken down by entity."""

from app.sync.splynx_parts.locations import sync_locations
from app.sync.splynx_parts.customers import sync_customers
from app.sync.splynx_parts.services import sync_services
from app.sync.splynx_parts.invoices import sync_invoices
from app.sync.splynx_parts.payments import sync_payments
from app.sync.splynx_parts.credit_notes import sync_credit_notes
from app.sync.splynx_parts.tickets import sync_tickets
from app.sync.splynx_parts.tariffs import sync_tariffs
from app.sync.splynx_parts.routers import sync_routers
from app.sync.splynx_parts.customer_notes import sync_customer_notes
from app.sync.splynx_parts.administrators import sync_administrators
from app.sync.splynx_parts.network_monitors import sync_network_monitors
from app.sync.splynx_parts.leads import sync_leads
from app.sync.splynx_parts.ipv4_addresses import sync_ipv4_addresses
from app.sync.splynx_parts.ticket_messages import sync_ticket_messages
from app.sync.splynx_parts.transaction_categories import sync_transaction_categories
from app.sync.splynx_parts.ipv4_networks import sync_ipv4_networks
from app.sync.splynx_parts.ipv6_networks import sync_ipv6_networks
from app.sync.splynx_parts.payment_methods import sync_payment_methods

__all__ = [
    "sync_locations",
    "sync_customers",
    "sync_services",
    "sync_invoices",
    "sync_payments",
    "sync_credit_notes",
    "sync_tickets",
    "sync_tariffs",
    "sync_routers",
    "sync_customer_notes",
    "sync_administrators",
    "sync_network_monitors",
    "sync_leads",
    "sync_ipv4_addresses",
    "sync_ticket_messages",
    "sync_transaction_categories",
    "sync_ipv4_networks",
    "sync_ipv6_networks",
    "sync_payment_methods",
]
