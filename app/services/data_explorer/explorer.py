"""Data Explorer Service.

Provides functionality to explore database tables, run queries,
and check data quality.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, TYPE_CHECKING, cast

from sqlalchemy import func, inspect, or_
from sqlalchemy.orm import Session

from app.services.errors import NotFoundError, ValidationError
from .table_registry import (
    TABLES,
    TABLE_CATEGORIES,
    TABLE_TO_CATEGORY,
    get_date_columns,
    get_model_columns,
    is_valid_table,
)
from .explorer_types import (
    ExploreFilters,
    ExportFilters,
    TableInfo,
    TableListResult,
    ExploreResult,
    TableStats,
    ExportResult,
    SearchResult,
    DataQualityReport,
    QueryRequest,
    QueryResult,
)

if TYPE_CHECKING:
    from app.auth import Principal

# Models needed for specific queries
from app.models.party import Party, CustomerAccount
from app.models.subscription import Subscription
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.conversation import Conversation
from app.models.pop import Pop
from app.models.employee import Employee
from app.models.credit_note import CreditNote
from app.models.ticket import Ticket
from app.models.project import Project
from app.models.tariff import Tariff
from app.models.router import Router
from app.models.lead import Lead
from app.models.network_monitor import NetworkMonitor
from app.models.ipv4_network import IPv4Network
from app.models.ipv4_address import IPv4Address
from app.models.administrator import Administrator
from app.models.accounting import (
    Account,
    JournalEntry,
    GLEntry,
    PurchaseInvoice,
)


class DataExplorerService:
    """Service for exploring database tables and data quality.

    All read-only operations. No transaction control needed.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Table Discovery
    # -------------------------------------------------------------------------

    def list_tables(self) -> TableListResult:
        """List all available tables with record counts, organized by category."""
        tables: Dict[str, TableInfo] = {}
        by_category: Dict[str, List[TableInfo]] = {}

        for name, model in TABLES.items():
            count = self.db.query(model).count()
            columns = get_model_columns(model)
            date_cols = get_date_columns(model)
            category = TABLE_TO_CATEGORY.get(name, "other")

            table_info = TableInfo(
                name=name,
                count=count,
                columns=columns,
                date_columns=date_cols,
                category=category,
                category_label=TABLE_CATEGORIES.get(category, "Other"),
            )
            tables[name] = table_info

            if category not in by_category:
                by_category[category] = []
            by_category[category].append(table_info)

        return TableListResult(
            tables=tables,
            categories=TABLE_CATEGORIES,
            by_category=by_category,
            total_tables=len(tables),
            total_records=sum(t.count for t in tables.values()),
        )

    def get_table_info(self, table_name: str) -> TableInfo:
        """Get information about a specific table."""
        if not is_valid_table(table_name):
            raise NotFoundError(f"Table not found: {table_name}")

        model = TABLES[table_name]
        count = self.db.query(model).count()
        columns = get_model_columns(model)
        date_cols = get_date_columns(model)
        category = TABLE_TO_CATEGORY.get(table_name, "other")

        return TableInfo(
            name=table_name,
            count=count,
            columns=columns,
            date_columns=date_cols,
            category=category,
            category_label=TABLE_CATEGORIES.get(category, "Other"),
        )

    # -------------------------------------------------------------------------
    # Data Exploration
    # -------------------------------------------------------------------------

    def explore_table(
        self,
        table_name: str,
        filters: ExploreFilters,
        limit: int = 50,
        offset: int = 0,
    ) -> ExploreResult:
        """Explore data in a specific table with date filtering and search."""
        if not is_valid_table(table_name):
            raise NotFoundError(f"Table not found: {table_name}")

        model = TABLES[table_name]

        # Security: Whitelist allowed columns for ordering and date filtering
        allowed_order_columns = {"id", "created_at", "updated_at", "name", "status", "created", "modified"}
        allowed_date_columns = {"created_at", "updated_at", "created", "modified", "posting_date", "due_date", "start_date", "end_date", "date"}

        # Validate order_by against whitelist
        if filters.order_by and filters.order_by not in allowed_order_columns:
            if not hasattr(model, filters.order_by):
                raise ValidationError(f"Invalid order_by column: {filters.order_by}")

        # Validate date_column against whitelist
        if filters.date_column and filters.date_column not in allowed_date_columns:
            actual_date_cols = get_date_columns(model)
            if filters.date_column not in actual_date_cols:
                raise ValidationError(f"Invalid date_column: {filters.date_column}")

        query = self.db.query(model)

        # Apply date filtering
        if filters.date_column and filters.start_date and filters.end_date:
            col = getattr(model, filters.date_column, None)
            if col is None:
                raise ValidationError(f"Invalid date column: {filters.date_column}")
            start_dt = datetime.strptime(filters.start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(filters.end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(col >= start_dt, col <= end_dt)

        # Apply search (search in string columns)
        if filters.search:
            search_conditions = []
            for column in inspect(model).mapper.column_attrs:
                col = getattr(model, column.key)
                if hasattr(col, 'type') and hasattr(col.type, 'python_type'):
                    if col.type.python_type == str:
                        search_conditions.append(col.ilike(f"%{filters.search}%"))
            if search_conditions:
                query = query.filter(or_(*search_conditions))

        # Apply ordering
        if filters.order_by:
            column = cast(Any, getattr(model, filters.order_by, None))
            if column is None:
                raise ValidationError(f"Invalid column: {filters.order_by}")
            if filters.order_dir == "desc":
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())
        else:
            # Default order by id desc
            if hasattr(model, "id"):
                query = query.order_by(model.id.desc())

        total = query.count()
        records = query.offset(offset).limit(limit).all()

        # Convert to dict
        data = []
        for record in records:
            row = {}
            for column in inspect(model).mapper.column_attrs:
                value = getattr(record, column.key)
                row[column.key] = self._serialize_value(value)
            data.append(row)

        return ExploreResult(
            table=table_name,
            total=total,
            limit=limit,
            offset=offset,
            date_columns=get_date_columns(model),
            columns=get_model_columns(model),
            filters_applied={
                "date_column": filters.date_column,
                "start_date": filters.start_date,
                "end_date": filters.end_date,
                "search": filters.search,
            },
            data=data,
        )

    def get_table_stats(self, table_name: str) -> TableStats:
        """Get statistics for a table."""
        if not is_valid_table(table_name):
            raise NotFoundError(f"Table not found: {table_name}")

        model = TABLES[table_name]
        total_records = self.db.query(model).count()
        stats: Dict[str, Any] = {}

        # Add specific stats based on table
        if table_name == "customer_accounts":
            stats["by_status"] = self._get_enum_counts(CustomerAccount, "status")
            stats["by_tier"] = self._get_enum_counts(CustomerAccount, "tier")

        elif table_name == "parties":
            stats["by_type"] = self._get_enum_counts(Party, "type")
            stats["by_status"] = self._get_enum_counts(Party, "status")

        elif table_name == "subscriptions":
            stats["by_status"] = self._get_enum_counts(Subscription, "status")
            stats["by_plan"] = {
                row.plan_name: int(getattr(row, "count", 0) or 0)
                for row in self.db.query(Subscription.plan_name, func.count(Subscription.id).label("count"))
                .group_by(Subscription.plan_name)
                .order_by(func.count(Subscription.id).desc())
                .limit(20)
                .all()
            }

        elif table_name == "invoices":
            stats["by_status"] = self._get_enum_counts(Invoice, "status")
            total_amount = self.db.query(func.sum(Invoice.total_amount)).scalar()
            total_paid = self.db.query(func.sum(Invoice.amount_paid)).scalar()
            stats["total_invoiced"] = float(total_amount or 0)
            stats["total_paid"] = float(total_paid or 0)

        elif table_name == "credit_notes":
            stats["by_status"] = self._get_enum_counts(CreditNote, "status")
            total_amount = self.db.query(func.sum(CreditNote.amount)).scalar()
            stats["total_credit_notes"] = float(total_amount or 0)

        elif table_name == "payments":
            stats["by_method"] = self._get_enum_counts(Payment, "payment_method")
            total = self.db.query(func.sum(Payment.amount)).scalar()
            stats["total_payments"] = float(total or 0)

        elif table_name == "conversations":
            stats["by_status"] = self._get_enum_counts(Conversation, "status")
            stats["by_channel"] = {
                row.channel: int(getattr(row, "count", 0) or 0)
                for row in self.db.query(Conversation.channel, func.count(Conversation.id).label("count"))
                .group_by(Conversation.channel)
                .all()
                if row.channel
            }

        elif table_name == "pops":
            stats["active"] = self.db.query(Pop).filter(Pop.is_active.is_(True)).count()
            stats["inactive"] = self.db.query(Pop).filter(Pop.is_active.is_(False)).count()

        elif table_name == "employees":
            stats["by_department"] = {
                row.department: int(getattr(row, "count", 0) or 0)
                for row in self.db.query(Employee.department, func.count(Employee.id).label("count"))
                .group_by(Employee.department)
                .all()
                if row.department
            }
            stats["by_status"] = self._get_enum_counts(Employee, "status")

        elif table_name == "tickets":
            stats["by_status"] = self._get_enum_counts(Ticket, "status")
            stats["by_priority"] = self._get_enum_counts(Ticket, "priority")
            stats["by_source"] = self._get_enum_counts(Ticket, "source")

        elif table_name == "projects":
            stats["by_status"] = self._get_enum_counts(Project, "status")
            stats["with_customer_account"] = self.db.query(Project).filter(Project.customer_account_id.isnot(None)).count()
            stats["with_manager"] = self.db.query(Project).filter(Project.project_manager_id.isnot(None)).count()

        elif table_name == "tariffs":
            stats["by_type"] = self._get_enum_counts(Tariff, "tariff_type")
            stats["enabled"] = self.db.query(Tariff).filter(Tariff.enabled.is_(True)).count()

        elif table_name == "routers":
            stats["by_nas_type"] = {
                str(row.nas_type): int(getattr(row, "count", 0) or 0)
                for row in self.db.query(Router.nas_type, func.count(Router.id).label("count"))
                .group_by(Router.nas_type)
                .all()
                if row.nas_type is not None
            }
            stats["with_pop"] = self.db.query(Router).filter(Router.pop_id.isnot(None)).count()

        elif table_name == "leads":
            stats["by_status"] = {
                row.status: int(getattr(row, "count", 0) or 0)
                for row in self.db.query(Lead.status, func.count(Lead.id).label("count"))
                .group_by(Lead.status)
                .all()
                if row.status
            }
            stats["converted"] = self.db.query(Lead).filter(Lead.customer_account_id.isnot(None)).count()

        elif table_name == "network_monitors":
            stats["by_ping_state"] = self._get_enum_counts(NetworkMonitor, "ping_state")
            stats["active"] = self.db.query(NetworkMonitor).filter(NetworkMonitor.active.is_(True)).count()

        elif table_name == "ipv4_networks":
            stats["by_type"] = {
                row.network_type: int(getattr(row, "count", 0) or 0)
                for row in self.db.query(IPv4Network.network_type, func.count(IPv4Network.id).label("count"))
                .group_by(IPv4Network.network_type)
                .all()
                if row.network_type
            }
            stats["by_usage"] = {
                row.type_of_usage: int(getattr(row, "count", 0) or 0)
                for row in self.db.query(IPv4Network.type_of_usage, func.count(IPv4Network.id).label("count"))
                .group_by(IPv4Network.type_of_usage)
                .all()
                if row.type_of_usage
            }

        elif table_name == "ipv4_addresses":
            stats["used"] = self.db.query(IPv4Address).filter(IPv4Address.is_used.is_(True)).count()
            stats["available"] = self.db.query(IPv4Address).filter(IPv4Address.is_used.is_(False)).count()
            stats["assigned_to_party"] = self.db.query(IPv4Address).filter(IPv4Address.party_id.isnot(None)).count()

        elif table_name == "accounts":
            stats["by_account_type"] = {
                row.account_type: int(getattr(row, "count", 0) or 0)
                for row in self.db.query(Account.account_type, func.count(Account.id).label("count"))
                .group_by(Account.account_type)
                .all()
                if row.account_type
            }
            stats["by_root_type"] = {
                row.root_type: int(getattr(row, "count", 0) or 0)
                for row in self.db.query(Account.root_type, func.count(Account.id).label("count"))
                .group_by(Account.root_type)
                .all()
                if row.root_type
            }

        elif table_name == "journal_entries":
            total_debit = self.db.query(func.sum(JournalEntry.total_debit)).scalar()
            total_credit = self.db.query(func.sum(JournalEntry.total_credit)).scalar()
            stats["total_debit"] = float(total_debit or 0)
            stats["total_credit"] = float(total_credit or 0)

        elif table_name == "gl_entries":
            total_debit = self.db.query(func.sum(GLEntry.debit)).scalar()
            total_credit = self.db.query(func.sum(GLEntry.credit)).scalar()
            stats["total_debit"] = float(total_debit or 0)
            stats["total_credit"] = float(total_credit or 0)

        elif table_name == "purchase_invoices":
            stats["by_status"] = {
                row.status: int(getattr(row, "count", 0) or 0)
                for row in self.db.query(PurchaseInvoice.status, func.count(PurchaseInvoice.id).label("count"))
                .group_by(PurchaseInvoice.status)
                .all()
                if row.status
            }
            total = self.db.query(func.sum(PurchaseInvoice.grand_total)).scalar()
            stats["total_amount"] = float(total or 0)

        elif table_name == "administrators":
            stats["by_role"] = {
                row.role_name: int(getattr(row, "count", 0) or 0)
                for row in self.db.query(Administrator.role_name, func.count(Administrator.id).label("count"))
                .group_by(Administrator.role_name)
                .all()
                if row.role_name
            }

        return TableStats(
            table=table_name,
            total_records=total_records,
            stats=stats,
        )

    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------

    def export_table(
        self,
        table_name: str,
        format: str,
        filters: ExportFilters,
    ) -> ExportResult:
        """Export table data as CSV or JSON with optional filtering."""
        if not is_valid_table(table_name):
            raise NotFoundError(f"Table not found: {table_name}")

        if format not in ("csv", "json"):
            raise ValidationError(f"Invalid format: {format}. Use 'csv' or 'json'.")

        model = TABLES[table_name]
        query = self.db.query(model)

        # Apply date filtering
        if filters.date_column and filters.start_date and filters.end_date:
            col = getattr(model, filters.date_column, None)
            if col is None:
                raise ValidationError(f"Invalid date column: {filters.date_column}")
            start_dt = datetime.strptime(filters.start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(filters.end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(col >= start_dt, col <= end_dt)

        # Apply search
        if filters.search:
            search_conditions = []
            for column in inspect(model).mapper.column_attrs:
                col = getattr(model, column.key)
                if hasattr(col, 'type') and hasattr(col.type, 'python_type'):
                    if col.type.python_type == str:
                        search_conditions.append(col.ilike(f"%{filters.search}%"))
            if search_conditions:
                query = query.filter(or_(*search_conditions))

        # Default order by id desc
        if hasattr(model, "id"):
            query = query.order_by(model.id.desc())

        # Limit to 10000 records for export to prevent memory issues
        records = query.limit(10000).all()
        columns = get_model_columns(model)

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            for record in records:
                row = []
                for col in columns:
                    value = getattr(record, col)
                    row.append(self._serialize_value(value))
                writer.writerow(row)

            output.seek(0)
            return ExportResult(
                content=output.getvalue(),
                filename=f"{table_name}_export.csv",
                media_type="text/csv",
            )
        else:  # json
            json_data: List[Dict[str, Any]] = []
            for record in records:
                json_row: Dict[str, Any] = {}
                for col in columns:
                    value = getattr(record, col)
                    json_row[col] = self._serialize_value(value)
                json_data.append(json_row)

            json_output: str = json.dumps(json_data, indent=2, default=str)
            return ExportResult(
                content=json_output,
                filename=f"{table_name}_export.json",
                media_type="application/json",
            )

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    def search_all(self, query: str, limit: int = 50) -> SearchResult:
        """Search across all major tables."""
        search_term = f"%{query}%"

        # Search parties
        parties = (
            self.db.query(Party)
            .filter(
                Party.name.ilike(search_term)
                | Party.primary_email.ilike(search_term)
                | Party.primary_phone.ilike(search_term)
            )
            .limit(limit)
            .all()
        )
        parties_data = [
            {
                "id": p.id,
                "name": p.name,
                "email": p.primary_email,
                "phone": p.primary_phone,
                "status": p.status,
            }
            for p in parties
        ]

        # Search customer accounts
        customer_accounts = (
            self.db.query(CustomerAccount)
            .filter(
                CustomerAccount.account_number.ilike(search_term)
                | CustomerAccount.billing_email.ilike(search_term)
            )
            .limit(limit)
            .all()
        )
        accounts_data = [
            {
                "id": c.id,
                "account_number": c.account_number,
                "billing_email": c.billing_email,
                "status": c.status,
            }
            for c in customer_accounts
        ]

        # Search invoices
        invoices = (
            self.db.query(Invoice)
            .filter(Invoice.invoice_number.ilike(search_term))
            .limit(limit)
            .all()
        )
        invoices_data = [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "total_amount": str(inv.total_amount),
                "status": inv.status.value,
            }
            for inv in invoices
        ]

        # Search employees
        employees = (
            self.db.query(Employee)
            .filter(
                Employee.name.ilike(search_term)
                | Employee.email.ilike(search_term)
            )
            .limit(limit)
            .all()
        )
        employees_data = [
            {
                "id": e.id,
                "name": e.name,
                "email": e.email,
                "department": e.department,
            }
            for e in employees
        ]

        # Search POPs
        pops = (
            self.db.query(Pop)
            .filter(
                Pop.name.ilike(search_term)
                | Pop.code.ilike(search_term)
            )
            .limit(limit)
            .all()
        )
        pops_data = [
            {
                "id": p.id,
                "name": p.name,
                "code": p.code,
            }
            for p in pops
        ]

        return SearchResult(
            parties=parties_data,
            customer_accounts=accounts_data,
            invoices=invoices_data,
            employees=employees_data,
            pops=pops_data,
        )

    # -------------------------------------------------------------------------
    # Data Quality
    # -------------------------------------------------------------------------

    def check_data_quality(self) -> DataQualityReport:
        """Check data quality and completeness across all tables."""
        # Parties
        total_parties = self.db.query(Party).count()
        parties_with_email = self.db.query(Party).filter(Party.primary_email.isnot(None)).count()
        parties_with_phone = self.db.query(Party).filter(Party.primary_phone.isnot(None)).count()

        parties_report = {
            "total": total_parties,
            "completeness": {
                "has_email": parties_with_email,
                "has_phone": parties_with_phone,
            },
            "quality_score": round(
                (parties_with_email + parties_with_phone)
                / (total_parties * 2)
                * 100
                if total_parties > 0
                else 0,
                2,
            ),
        }

        # Customer accounts
        total_accounts = self.db.query(CustomerAccount).count()
        accounts_with_billing_email = self.db.query(CustomerAccount).filter(
            CustomerAccount.billing_email.isnot(None)
        ).count()
        accounts_linked_splynx = self.db.query(CustomerAccount).filter(
            CustomerAccount.external_ids["splynx_id"].astext.isnot(None)
        ).count()
        accounts_linked_erpnext = self.db.query(CustomerAccount).filter(
            CustomerAccount.external_ids["erpnext_id"].astext.isnot(None)
        ).count()
        accounts_linked_chatwoot = self.db.query(CustomerAccount).filter(
            CustomerAccount.external_ids["chatwoot_id"].astext.isnot(None)
        ).count()

        accounts_report = {
            "total": total_accounts,
            "completeness": {
                "has_billing_email": accounts_with_billing_email,
            },
            "linkage": {
                "linked_to_splynx": accounts_linked_splynx,
                "linked_to_erpnext": accounts_linked_erpnext,
                "linked_to_chatwoot": accounts_linked_chatwoot,
            },
            "quality_score": round(
                accounts_with_billing_email / total_accounts * 100 if total_accounts > 0 else 0,
                2,
            ),
        }

        # Invoices
        total_invoices = self.db.query(Invoice).count()
        invoices_with_customer = self.db.query(Invoice).filter(Invoice.customer_account_id.isnot(None)).count()

        invoices_report = {
            "total": total_invoices,
            "linked_to_customer": invoices_with_customer,
            "unlinked": total_invoices - invoices_with_customer,
        }

        # Conversations
        total_conversations = self.db.query(Conversation).count()
        conversations_with_customer = self.db.query(Conversation).filter(Conversation.customer_account_id.isnot(None)).count()

        conversations_report = {
            "total": total_conversations,
            "linked_to_customer": conversations_with_customer,
            "unlinked": total_conversations - conversations_with_customer,
        }

        # Overall data health
        total_records = sum([
            total_parties,
            total_accounts,
            self.db.query(Subscription).count(),
            total_invoices,
            self.db.query(Payment).count(),
            total_conversations,
        ])

        summary = {
            "total_records": total_records,
            "last_sync_check": datetime.now(timezone.utc).isoformat(),
        }

        return DataQualityReport(
            parties=parties_report,
            customer_accounts=accounts_report,
            invoices=invoices_report,
            conversations=conversations_report,
            summary=summary,
        )

    # -------------------------------------------------------------------------
    # Custom Queries
    # -------------------------------------------------------------------------

    def run_query(self, request: QueryRequest) -> QueryResult:
        """Run a custom query with filters, grouping, and aggregation."""
        if not is_valid_table(request.table):
            raise NotFoundError(f"Table not found: {request.table}")

        model = TABLES[request.table]

        # Handle grouping and aggregation
        if request.group_by and request.aggregate:
            select_columns = []
            for col_name in request.group_by:
                column = getattr(model, col_name, None)
                if column:
                    select_columns.append(column)

            for col_name, agg_func in request.aggregate.items():
                column = getattr(model, col_name, None)
                if column:
                    if agg_func == "count":
                        select_columns.append(func.count(column).label(f"{col_name}_count"))
                    elif agg_func == "sum":
                        select_columns.append(func.sum(column).label(f"{col_name}_sum"))
                    elif agg_func == "avg":
                        select_columns.append(func.avg(column).label(f"{col_name}_avg"))
                    elif agg_func == "min":
                        select_columns.append(func.min(column).label(f"{col_name}_min"))
                    elif agg_func == "max":
                        select_columns.append(func.max(column).label(f"{col_name}_max"))

            query = self.db.query(*select_columns)
            query = self._apply_filters(query, model, request.filters)

            for col_name in request.group_by:
                column = getattr(model, col_name, None)
                if column:
                    query = query.group_by(column)

            results = query.limit(request.limit).all()

            # Convert results to dict
            data = []
            for row in results:
                row_dict = {}
                for i, col_name in enumerate(request.group_by):
                    value = row[i]
                    if hasattr(value, "value"):
                        value = value.value
                    row_dict[col_name] = value

                for j, (col_name, agg_func) in enumerate(request.aggregate.items()):
                    row_dict[f"{col_name}_{agg_func}"] = float(row[len(request.group_by) + j] or 0)
                data.append(row_dict)

            return QueryResult(data=data, grouped=True)

        # Regular query (no aggregation)
        query = self.db.query(model)
        query = self._apply_filters(query, model, request.filters)

        total = query.count()
        records = query.limit(request.limit).all()

        data = []
        for record in records:
            row = {}
            for column in inspect(model).mapper.column_attrs:
                value = getattr(record, column.key)
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif hasattr(value, "value"):
                    value = value.value
                row[column.key] = value
            data.append(row)

        return QueryResult(data=data, grouped=False, total=total, limit=request.limit)

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value for JSON output."""
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, Decimal):
            return float(value)
        elif hasattr(value, "value"):  # Enum
            return value.value
        return value

    def _get_enum_counts(self, model: Any, field_name: str) -> Dict[str, int]:
        """Get counts grouped by an enum field."""
        field = getattr(model, field_name, None)
        if field is None:
            return {}

        rows = (
            self.db.query(field, func.count(model.id).label("count"))
            .group_by(field)
            .all()
        )

        result = {}
        for row in rows:
            key = row[0]
            if key is None:
                continue
            if hasattr(key, "value"):
                key = key.value
            result[str(key)] = int(row.count or 0)
        return result

    def _apply_filters(self, query: Any, model: Any, filters: Optional[Dict[str, Any]]) -> Any:
        """Apply filters to a query, handling both simple values and operator dicts."""
        if not filters:
            return query

        for column_name, value in filters.items():
            column = getattr(model, column_name, None)
            if column is None:
                continue

            if isinstance(value, dict):
                # Handle operators: {"gt": 100, "lt": 500}
                for op, val in value.items():
                    if op == "gt":
                        query = query.filter(column > val)
                    elif op == "gte":
                        query = query.filter(column >= val)
                    elif op == "lt":
                        query = query.filter(column < val)
                    elif op == "lte":
                        query = query.filter(column <= val)
                    elif op == "eq":
                        query = query.filter(column == val)
                    elif op == "ne":
                        query = query.filter(column != val)
                    elif op == "like":
                        query = query.filter(column.ilike(f"%{val}%"))
                    elif op == "in":
                        query = query.filter(column.in_(val))
            else:
                # Simple equality
                query = query.filter(column == value)

        return query
