"""AP Aging API endpoints."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from app.services.purchasing import APAgingService

from ._deps import (
    get_aging_service,
    RequireRead,
    parse_date,
)

router = APIRouter(tags=["purchasing"])


@router.get("/aging", dependencies=[RequireRead])
async def get_ap_aging(
    as_of_date: Optional[str] = None,
    supplier: Optional[str] = None,
    currency: Optional[str] = None,
    service: APAgingService = Depends(get_aging_service),
) -> Dict[str, Any]:
    """Get accounts payable aging buckets."""
    return service.get_aging_report(
        as_of_date=parse_date(as_of_date, "as_of_date"),
        supplier=supplier,
        currency=currency,
    )
