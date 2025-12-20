"""ERPNext sync functions organized by domain.

This package contains sync functions for ERPNext entities organized by business domain:
- accounting: Financial documents, GL, bank transactions
- sales: Customers, orders, quotations, leads
- inventory: Items, item groups
- hr: Employees, departments, teams
- support: Tickets, projects
"""

from app.sync.erpnext_parts.accounting import (
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
)
from app.sync.erpnext_parts.hr import (
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
)
from app.sync.erpnext_parts.inventory import (
    sync_item_groups,
    sync_items,
)
from app.sync.erpnext_parts.sales import (
    sync_customer_groups,
    sync_customers,
    sync_erpnext_leads,
    sync_quotations,
    sync_sales_orders,
    sync_sales_persons,
    sync_territories,
)
from app.sync.erpnext_parts.support import (
    sync_hd_tickets,
    sync_projects,
)

__all__ = [
    # Accounting
    "sync_accounts",
    "sync_bank_accounts",
    "sync_bank_transactions",
    "sync_cost_centers",
    "sync_expenses",
    "sync_fiscal_years",
    "sync_gl_entries",
    "sync_invoices",
    "sync_journal_entries",
    "sync_modes_of_payment",
    "sync_payments",
    "sync_purchase_invoices",
    "sync_suppliers",
    # HR
    "resolve_employee_relationships",
    "resolve_sales_person_employees",
    "sync_attendances",
    "sync_departments",
    "sync_designations",
    "sync_employees",
    "sync_erpnext_users",
    "sync_hd_teams",
    "sync_leave_allocations",
    "sync_leave_applications",
    "sync_leave_types",
    "sync_payroll_entries",
    "sync_salary_components",
    "sync_salary_slips",
    "sync_salary_structures",
    # Inventory
    "sync_item_groups",
    "sync_items",
    # Sales
    "sync_customer_groups",
    "sync_customers",
    "sync_erpnext_leads",
    "sync_quotations",
    "sync_sales_orders",
    "sync_sales_persons",
    "sync_territories",
    # Support
    "sync_hd_tickets",
    "sync_projects",
]
