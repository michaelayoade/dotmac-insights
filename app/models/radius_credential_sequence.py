"""RADIUS credential sequence model.

Tracks sequential counters for RADIUS username generation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RADIUSCredentialSequence(Base):
    """Tracks sequential counters for RADIUS username generation.

    Used when username format is 'sequential' to generate usernames
    like USER0001, USER0002, etc.
    """

    __tablename__ = "radius_credential_sequences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Sequence identifier (e.g., "default", or could be per-company/tariff)
    sequence_name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

    # Current counter value
    current_value: Mapped[int] = mapped_column(default=0, nullable=False)

    # Configuration (stored here for quick access)
    prefix: Mapped[str] = mapped_column(String(50), nullable=False, default="USER")
    padding_length: Mapped[int] = mapped_column(default=4, nullable=False)

    # Optional company scope for multi-tenant deployments
    # NOTE: Currently unused - service uses sequence_name="default" for all companies.
    # To enable per-company sequences, update RADIUSCredentialService._generate_sequential_username
    # to use sequence_name=f"company_{company_id}" or similar.
    company: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        next_val = self.current_value + 1
        next_username = f"{self.prefix}{str(next_val).zfill(self.padding_length)}"
        return f"<RADIUSCredentialSequence {self.sequence_name}: next={next_username}>"

    def get_next_username(self) -> str:
        """Get the next username in the sequence without incrementing.

        Returns:
            The next username that would be generated.
        """
        next_val = self.current_value + 1
        return f"{self.prefix}{str(next_val).zfill(self.padding_length)}"

    def increment_and_get(self) -> str:
        """Increment the counter and return the new username.

        Note: This should be called within a transaction with FOR UPDATE lock.

        Returns:
            The generated username.
        """
        self.current_value += 1
        return f"{self.prefix}{str(self.current_value).zfill(self.padding_length)}"
