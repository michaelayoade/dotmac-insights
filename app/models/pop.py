from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.expense import Expense


class Pop(Base):
    """Point of Presence - Network locations/sites."""

    __tablename__ = "pops"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External IDs
    splynx_id: Mapped[Optional[int]] = mapped_column(unique=True, index=True, nullable=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Location
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customers: Mapped[List[Customer]] = relationship(back_populates="pop")
    expenses: Mapped[List[Expense]] = relationship(back_populates="pop")

    def __repr__(self) -> str:
        return f"<Pop {self.name}>"
