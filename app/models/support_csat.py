"""CSAT (Customer Satisfaction) survey models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket
    from app.models.customer import Customer
    from app.models.agent import Agent


class SurveyTrigger(str, Enum):
    """When to send the survey."""
    TICKET_RESOLVED = "ticket_resolved"
    TICKET_CLOSED = "ticket_closed"
    MANUAL = "manual"


class SurveyType(str, Enum):
    """Type of satisfaction survey."""
    CSAT = "csat"  # Customer Satisfaction (1-5 scale)
    NPS = "nps"    # Net Promoter Score (0-10 scale)
    CES = "ces"    # Customer Effort Score (1-7 scale)


class CSATSurvey(Base):
    """Customer satisfaction survey template.

    Defines when and how surveys are sent to customers.
    Supports different survey types (CSAT, NPS, CES).

    Questions format:
    [
        {"id": "q1", "text": "How satisfied are you?", "type": "rating", "required": true},
        {"id": "q2", "text": "What could we improve?", "type": "text", "required": false}
    ]
    """

    __tablename__ = "csat_surveys"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Survey configuration
    survey_type: Mapped[str] = mapped_column(String(20), default=SurveyType.CSAT.value, index=True)
    trigger: Mapped[str] = mapped_column(String(30), default=SurveyTrigger.TICKET_RESOLVED.value, index=True)

    # Questions (JSON array)
    questions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timing
    delay_hours: Mapped[int] = mapped_column(Integer, default=0)  # Delay after trigger

    # Delivery method
    send_via: Mapped[str] = mapped_column(String(50), default="email")  # email, in_app, both

    # Conditions for sending (JSON - matches ticket criteria)
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    responses: Mapped[List["CSATResponse"]] = relationship(back_populates="survey")

    def __repr__(self) -> str:
        return f"<CSATSurvey {self.name} ({self.survey_type})>"


class CSATResponse(Base):
    """Customer response to a satisfaction survey."""

    __tablename__ = "csat_responses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # References
    survey_id: Mapped[int] = mapped_column(
        ForeignKey("csat_surveys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Primary rating (depends on survey type)
    # CSAT: 1-5, NPS: 0-10, CES: 1-7
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Detailed answers (JSON - keyed by question ID)
    answers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Free-form feedback
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Tracking
    sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    response_channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Unique token for response link
    response_token: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    # Relationships
    survey: Mapped["CSATSurvey"] = relationship(back_populates="responses")
    ticket: Mapped[Optional["Ticket"]] = relationship()
    customer: Mapped[Optional["Customer"]] = relationship()
    agent: Mapped[Optional["Agent"]] = relationship()

    def __repr__(self) -> str:
        return f"<CSATResponse survey={self.survey_id} rating={self.rating}>"
