"""Asset Settings Model

Configuration for asset management including depreciation defaults and alert thresholds.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DepreciationMethod(str, Enum):
    """Depreciation calculation method"""
    STRAIGHT_LINE = "straight_line"
    DOUBLE_DECLINING_BALANCE = "double_declining_balance"
    WRITTEN_DOWN_VALUE = "written_down_value"
    MANUAL = "manual"


class DepreciationPostingDate(str, Enum):
    """When to post depreciation entries"""
    LAST_DAY = "last_day"
    FIRST_DAY = "first_day"
    SCHEDULE_DATE = "schedule_date"


class AssetSettings(Base):
    """Global asset management settings.

    Stores default configurations for depreciation, CWIP accounting,
    and alert thresholds for maintenance/warranty/insurance.
    """

    __tablename__ = "asset_settings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Depreciation defaults
    default_depreciation_method: Mapped[str] = mapped_column(
        String(50), default=DepreciationMethod.STRAIGHT_LINE.value
    )
    default_finance_book: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    depreciation_posting_date: Mapped[str] = mapped_column(
        String(50), default=DepreciationPostingDate.LAST_DAY.value
    )
    auto_post_depreciation: Mapped[bool] = mapped_column(Boolean, default=False)

    # CWIP (Capital Work in Progress)
    enable_cwip_by_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Alert thresholds (days before event)
    maintenance_alert_days: Mapped[int] = mapped_column(Integer, default=7)
    warranty_alert_days: Mapped[int] = mapped_column(Integer, default=30)
    insurance_alert_days: Mapped[int] = mapped_column(Integer, default=30)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<AssetSettings id={self.id} company={self.company}>"
