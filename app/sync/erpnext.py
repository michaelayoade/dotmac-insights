"""ERPNext sync client - orchestrates syncing data from ERPNext ERP.

This module provides the ERPNextSync class which manages syncing data from
ERPNext to the local database. The actual sync logic is organized by domain
in the erpnext_parts subpackage.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
import structlog
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.models.sync_log import SyncSource
from app.sync.base import BaseSyncClient
from app.sync.erpnext_parts import (
    # Accounting
    sync_accounts,
    sync_bank_accounts,
    sync_bank_transactions,
    sync_cost_centers,
    sync_expenses,
    sync_fiscal_years,
    sync_gl_entries,
    sync_invoices,
    sync_journal_entries,
    sync_modes_of_payment,
    sync_payments,
    sync_purchase_invoices,
    sync_suppliers,
    # HR
    resolve_employee_relationships,
    resolve_sales_person_employees,
    sync_attendances,
    sync_departments,
    sync_designations,
    sync_employees,
    sync_erpnext_users,
    sync_hd_teams,
    sync_leave_allocations,
    sync_leave_applications,
    sync_leave_types,
    sync_payroll_entries,
    sync_salary_components,
    sync_salary_slips,
    sync_salary_structures,
    # Inventory
    sync_item_groups,
    sync_items,
    # Sales
    sync_customer_groups,
    sync_customers,
    sync_erpnext_leads,
    sync_quotations,
    sync_sales_orders,
    sync_sales_persons,
    sync_territories,
    # Support
    sync_hd_tickets,
    sync_projects,
    # Assets & Vehicles
    sync_asset_categories,
    sync_assets,
    sync_vehicles,
)

logger = structlog.get_logger()


class ERPNextSync(BaseSyncClient):
    """Sync client for ERPNext ERP system.

    This class orchestrates syncing data from ERPNext to the local database.
    The actual sync logic is organized by domain in the erpnext_parts subpackage:
    - accounting.py: Financial documents, GL, bank transactions
    - sales.py: Customers, orders, quotations, leads
    - inventory.py: Items, item groups
    - hr.py: Employees, departments, teams
    - support.py: Tickets, projects
    """

    source = SyncSource.ERPNEXT

    def __init__(self, db: Session):
        super().__init__(db)
        self.base_url = settings.erpnext_api_url.rstrip("/")
        self.api_key = settings.erpnext_api_key
        self.api_secret = settings.erpnext_api_secret

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

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

    def _get_incremental_filter(
        self, entity_type: str, full_sync: bool
    ) -> Optional[Dict[str, Any]]:
        """Get modified filter for incremental sync.

        Returns a filter dict for ERPNext API to fetch only records modified
        since the last sync. Returns None if doing a full sync or no cursor exists.

        Args:
            entity_type: The entity type being synced (e.g., "customers", "invoices")
            full_sync: If True, returns None (no filter for full sync)

        Returns:
            Filter dict with modified >= timestamp, or None
        """
        if full_sync:
            # Full sync - reset cursor and fetch all
            self.reset_cursor(entity_type)
            return None

        cursor = self.get_cursor(entity_type)
        if cursor and cursor.last_modified_at:
            # Format for ERPNext: YYYY-MM-DD HH:MM:SS
            modified_since = cursor.last_modified_at.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                "incremental_sync_filter",
                entity_type=entity_type,
                modified_since=modified_since,
            )
            return {"modified": [">=", modified_since]}

        # No cursor - this is effectively a full sync
        logger.info(
            "incremental_sync_no_cursor",
            entity_type=entity_type,
            message="No cursor found, fetching all records",
        )
        return None

    def _update_sync_cursor(
        self,
        entity_type: str,
        records: List[Dict[str, Any]],
        records_count: int,
    ) -> None:
        """Update sync cursor with the latest modified timestamp from records.

        Args:
            entity_type: The entity type being synced
            records: List of records that were synced (each should have 'modified' field)
            records_count: Total count of records processed
        """
        if not records:
            return

        # Find the maximum modified timestamp from the records
        max_modified: Optional[str] = None
        for record in records:
            modified = record.get("modified")
            if modified:
                if max_modified is None or modified > max_modified:
                    max_modified = modified

        if max_modified:
            self.update_cursor(
                entity_type=entity_type,
                modified_at=max_modified,
                records_count=records_count,
            )
            logger.info(
                "sync_cursor_updated",
                entity_type=entity_type,
                last_modified=max_modified,
                records_count=records_count,
            )

    # -------------------------------------------------------------------------
    # HTTP methods
    # -------------------------------------------------------------------------

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
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make authenticated request to ERPNext API."""
        response = await client.request(
            method,
            f"{self.base_url}{endpoint}",
            headers=self._get_headers(),
            params=params,
            json=json_data,
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
        # URL encode the document name to handle special characters
        encoded_name = quote(name, safe="")
        data = await self._request(client, "GET", f"/api/resource/{doctype}/{encoded_name}")
        result: Dict[str, Any] = data.get("data", {}) if isinstance(data, dict) else {}
        return result

    # -------------------------------------------------------------------------
    # Connection test
    # -------------------------------------------------------------------------

    async def test_connection(self) -> bool:
        """Test if ERPNext API connection is working."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await self._fetch_doctype(client, "Company", limit_page_length=1)
            return True
        except Exception as e:
            logger.error("erpnext_connection_test_failed", error=str(e))
            return False

    # -------------------------------------------------------------------------
    # Full sync orchestrator
    # -------------------------------------------------------------------------

    async def sync_all(self, full_sync: bool = False):
        """Sync all entities from ERPNext.

        This includes core entities, accounting, sales, HR, and inventory data.
        """
        async with httpx.AsyncClient(timeout=180) as client:
            # Core entities
            await sync_customers(self, client, full_sync)
            await sync_employees(self, client, full_sync)
            await sync_invoices(self, client, full_sync)
            await sync_payments(self, client, full_sync)
            await sync_expenses(self, client, full_sync)
            await sync_hd_tickets(self, client, full_sync)
            await sync_projects(self, client, full_sync)

            # Accounting entities
            await sync_bank_accounts(self, client, full_sync)
            await sync_accounts(self, client, full_sync)
            await sync_journal_entries(self, client, full_sync)
            await sync_purchase_invoices(self, client, full_sync)
            await sync_gl_entries(self, client, full_sync)

            # Extended accounting
            await sync_suppliers(self, client, full_sync)
            await sync_cost_centers(self, client, full_sync)
            await sync_fiscal_years(self, client, full_sync)
            await sync_bank_transactions(self, client, full_sync)

            # Sales entities
            await sync_customer_groups(self, client, full_sync)
            await sync_territories(self, client, full_sync)
            await sync_sales_persons(self, client, full_sync)
            await sync_item_groups(self, client, full_sync)
            await sync_items(self, client, full_sync)
            await sync_erpnext_leads(self, client, full_sync)
            await sync_quotations(self, client, full_sync)
            await sync_sales_orders(self, client, full_sync)

            # HR entities
            await sync_departments(self, client, full_sync)
            await sync_designations(self, client, full_sync)
            await sync_erpnext_users(self, client, full_sync)
            await sync_hd_teams(self, client, full_sync)
            await sync_leave_types(self, client, full_sync)
            await sync_leave_allocations(self, client, full_sync)
            await sync_leave_applications(self, client, full_sync)
            await sync_attendances(self, client, full_sync)
            await sync_salary_components(self, client, full_sync)
            await sync_salary_structures(self, client, full_sync)
            await sync_payroll_entries(self, client, full_sync)
            await sync_salary_slips(self, client, full_sync)
            resolve_employee_relationships(self)
            resolve_sales_person_employees(self)

    # -------------------------------------------------------------------------
    # Task wrappers for Celery (creates own httpx client)
    # -------------------------------------------------------------------------

    async def sync_customers_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Customers with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_customers(self, client, full_sync)

    async def sync_invoices_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Sales Invoices with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_invoices(self, client, full_sync)

    async def sync_payments_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Payments with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_payments(self, client, full_sync)

    async def sync_expenses_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Expense Claims with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_expenses(self, client, full_sync)

    async def sync_hd_tickets_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs HD Tickets with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_hd_tickets(self, client, full_sync)

    async def sync_projects_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Projects with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_projects(self, client, full_sync)

    async def sync_accounting_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs core accounting data."""
        async with httpx.AsyncClient(timeout=180) as client:
            await sync_bank_accounts(self, client, full_sync)
            await sync_accounts(self, client, full_sync)
            await sync_journal_entries(self, client, full_sync)
            await sync_purchase_invoices(self, client, full_sync)
            await sync_gl_entries(self, client, full_sync)

    async def sync_extended_accounting_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs extended accounting data."""
        async with httpx.AsyncClient(timeout=180) as client:
            await sync_suppliers(self, client, full_sync)
            await sync_modes_of_payment(self, client, full_sync)
            await sync_cost_centers(self, client, full_sync)
            await sync_fiscal_years(self, client, full_sync)
            await sync_bank_transactions(self, client, full_sync)

    async def sync_bank_transactions_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Bank Transactions with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_bank_transactions(self, client, full_sync)

    async def sync_suppliers_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Suppliers with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_suppliers(self, client, full_sync)

    async def sync_modes_of_payment_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Modes of Payment with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_modes_of_payment(self, client, full_sync)

    async def sync_cost_centers_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Cost Centers with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_cost_centers(self, client, full_sync)

    async def sync_fiscal_years_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Fiscal Years with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_fiscal_years(self, client, full_sync)

    async def sync_sales_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs all sales-related data."""
        async with httpx.AsyncClient(timeout=180) as client:
            # Reference data first
            await sync_customer_groups(self, client, full_sync)
            await sync_territories(self, client, full_sync)
            await sync_sales_persons(self, client, full_sync)
            # Items
            await sync_item_groups(self, client, full_sync)
            await sync_items(self, client, full_sync)
            # Leads, quotes, orders
            await sync_erpnext_leads(self, client, full_sync)
            await sync_quotations(self, client, full_sync)
            await sync_sales_orders(self, client, full_sync)

    async def sync_sales_orders_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Sales Orders with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_sales_orders(self, client, full_sync)

    async def sync_quotations_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Quotations with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_quotations(self, client, full_sync)

    async def sync_erpnext_leads_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs ERPNext Leads with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_erpnext_leads(self, client, full_sync)

    async def sync_items_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Items with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_items(self, client, full_sync)

    async def sync_customer_groups_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Customer Groups with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_customer_groups(self, client, full_sync)

    async def sync_territories_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Territories with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_territories(self, client, full_sync)

    async def sync_sales_persons_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Sales Persons with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_sales_persons(self, client, full_sync)

    async def sync_item_groups_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Item Groups with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_item_groups(self, client, full_sync)

    async def sync_inventory_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs all inventory data."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_item_groups(self, client, full_sync)
            await sync_items(self, client, full_sync)

    async def sync_departments_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Departments with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_departments(self, client, full_sync)

    async def sync_designations_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Designations with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_designations(self, client, full_sync)

    async def sync_erpnext_users_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs ERPNext Users with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_erpnext_users(self, client, full_sync)

    async def sync_hd_teams_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs HD Teams with its own client."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_hd_teams(self, client, full_sync)

    async def sync_hr_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs all HR-related data."""
        async with httpx.AsyncClient(timeout=180) as client:
            await sync_employees(self, client, full_sync)
            # Sync reference data first
            await sync_departments(self, client, full_sync)
            await sync_designations(self, client, full_sync)
            # Then sync users and teams (which link to employees)
            await sync_erpnext_users(self, client, full_sync)
            await sync_hd_teams(self, client, full_sync)
            # Leave and attendance
            await sync_leave_types(self, client, full_sync)
            await sync_leave_allocations(self, client, full_sync)
            await sync_leave_applications(self, client, full_sync)
            await sync_attendances(self, client, full_sync)
            # Payroll configuration and runs
            await sync_salary_components(self, client, full_sync)
            await sync_salary_structures(self, client, full_sync)
            await sync_payroll_entries(self, client, full_sync)
            await sync_salary_slips(self, client, full_sync)
            # Resolve employee FK relationships
            resolve_employee_relationships(self)
            # Link sales persons to employees
            resolve_sales_person_employees(self)

    async def sync_assets_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Assets and Asset Categories."""
        async with httpx.AsyncClient(timeout=180) as client:
            await sync_asset_categories(self, client, full_sync)
            await sync_assets(self, client, full_sync)

    async def sync_vehicles_task(self, full_sync: bool = False):
        """Wrapper for Celery task - syncs Vehicles (Fleet Management)."""
        async with httpx.AsyncClient(timeout=60) as client:
            await sync_vehicles(self, client, full_sync)
