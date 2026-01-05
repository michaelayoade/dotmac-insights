"""Omnichannel channel service.

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models.omni import OmniChannel

if TYPE_CHECKING:
    from app.auth import Principal


class OmniChannelService:
    """Service for OmniChannel lookups."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    def list_active_channels(self) -> List[OmniChannel]:
        """List active channels for filters."""
        return (
            self.db.query(OmniChannel)
            .filter(OmniChannel.is_active == True)
            .order_by(OmniChannel.name.asc())
            .all()
        )
