"""Payment Terms models for due date calculation and payment scheduling."""
from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from app.database import Base


class PaymentTermsTemplate(Base):
    """
    Payment terms template for calculating due dates.

    Examples:
    - Net 30 (100% due in 30 days)
    - 2/10 Net 30 (2% discount if paid in 10 days, else full in 30)
    - 50% Now, 50% in 30 days
    """

    __tablename__ = "payment_terms_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Identification
    template_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    schedules: Mapped[List["PaymentTermsSchedule"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="PaymentTermsSchedule.idx",
    )

    def __repr__(self) -> str:
        return f"<PaymentTermsTemplate {self.template_name}>"


class PaymentTermsSchedule(Base):
    """
    Individual schedule line within a payment terms template.

    Each line represents a portion of payment due at a certain time.
    The sum of payment_percentage across all schedules should equal 100.
    """

    __tablename__ = "payment_terms_schedules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Parent link
    template_id: Mapped[int] = mapped_column(
        ForeignKey("payment_terms_templates.id"), nullable=False, index=True
    )

    # Payment timing
    credit_days: Mapped[int] = mapped_column(default=0)  # Days after invoice date
    credit_months: Mapped[int] = mapped_column(default=0)  # Months after invoice date
    day_of_month: Mapped[Optional[int]] = mapped_column(nullable=True)  # Specific day (1-31), overrides credit_days

    # Payment portion
    payment_percentage: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("100")
    )

    # Early payment discount
    discount_percentage: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0")
    )
    discount_days: Mapped[int] = mapped_column(default=0)  # Days within which discount applies

    # Description for this schedule line
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationship
    template: Mapped["PaymentTermsTemplate"] = relationship(back_populates="schedules")

    def __repr__(self) -> str:
        return f"<PaymentTermsSchedule {self.payment_percentage}% in {self.credit_days} days>"
