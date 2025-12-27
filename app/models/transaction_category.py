from __future__ import annotations

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from app.database import Base


class TransactionCategory(Base):
    """Transaction categories from Splynx finance module."""

    __tablename__ = "transaction_categories"

    id = Column(Integer, primary_key=True, index=True)

    # Splynx ID
    splynx_id = Column(Integer, unique=True, index=True, nullable=False)

    # Category info
    name = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    description = Column(String(500), nullable=True)

    # Category type: income, expense, transfer, etc.
    category_type = Column(String(50), nullable=True, index=True)

    # Accounting codes
    accounting_code = Column(String(100), nullable=True)
    tax_code = Column(String(50), nullable=True)

    # Settings
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)  # Built-in system category

    # Parent category for hierarchy
    parent_id = Column(Integer, nullable=True, index=True)

    # Display order
    sort_order = Column(Integer, default=0)

    # Dates
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<TransactionCategory {self.name} ({self.category_type})>"
