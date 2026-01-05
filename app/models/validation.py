"""Validation models and mixins."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SoftValidationMixin:
    """Marker mixin for soft validation scope."""

    __soft_validation_scope__ = "finance"

    @property
    def validation_scope(self) -> str:
        return getattr(self, "__soft_validation_scope__", "finance")

    @property
    def validation_model_name(self) -> str:
        return self.__class__.__name__

    @property
    def validation_record_id(self) -> Optional[int]:
        return getattr(self, "id", None)


class FinanceValidationIssue(Base):
    """Stored soft validation findings for finance models."""

    __tablename__ = "finance_validation_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    record_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'finance'"))
    issues: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("model_name", "record_id", name="uq_finance_validation_issue"),
        Index("ix_finance_validation_scope_detected", "scope", "detected_at"),
    )
