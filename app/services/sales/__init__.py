"""Sales services package.

Provides business logic for sales document management:
- QuotationService: Price quotation lifecycle management
- SalesOrderService: Sales order workflow and invoicing
- SalesAnalyticsService: Sales reporting and metrics
- SalesDashboardService: Real-time sales dashboard data
"""
from __future__ import annotations

from .quotations import QuotationService
from .orders import SalesOrderService
from .analytics import SalesAnalyticsService
from .dashboard import SalesDashboardService

__all__ = [
    "QuotationService",
    "SalesOrderService",
    "SalesAnalyticsService",
    "SalesDashboardService",
]
