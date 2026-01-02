"""Canned response service - business logic for canned response templates.

This service handles canned response management:
- CRUD operations for canned responses
- Scoping (personal, team, global)
- Variable rendering
- Usage tracking

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.support_canned import CannedResponse, CannedResponseScope
from app.models.agent import Agent, TeamMember
from app.models.omni import OmniConversation
from app.models.ticket import Ticket

from .types import (
    CannedResponseCreate,
    CannedResponseUpdate,
)
from .errors import (
    CannedResponseNotFoundError,
    DuplicateShortcodeError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["CannedResponseService"]

# Supported placeholder variables
SUPPORTED_VARIABLES = [
    "ticket.number",
    "ticket.subject",
    "ticket.status",
    "ticket.priority",
    "customer.name",
    "customer.email",
    "customer.company",
    "agent.name",
    "agent.email",
    "conversation.channel",
    "conversation.subject",
    "date",
    "time",
    "datetime",
]


class CannedResponseService:
    """Service for canned response management.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list(
        self,
        scope: Optional[str] = None,
        team_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        active_only: bool = True,
    ) -> List[CannedResponse]:
        """List canned responses with optional filtering.

        Args:
            scope: Filter by scope (personal, team, global).
            team_id: Filter by team ID (for team scope).
            agent_id: Filter by agent ID (for personal scope).
            category: Filter by category.
            search: Search in name and content.
            active_only: Only return active responses.

        Returns:
            List of CannedResponse instances.
        """
        query = self.db.query(CannedResponse)

        if active_only:
            query = query.filter(CannedResponse.is_active == True)

        if scope:
            query = query.filter(CannedResponse.scope == scope)

        if team_id:
            query = query.filter(CannedResponse.team_id == team_id)

        if agent_id:
            query = query.filter(CannedResponse.agent_id == agent_id)

        if category:
            query = query.filter(CannedResponse.category == category)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    CannedResponse.name.ilike(search_term),
                    CannedResponse.content.ilike(search_term),
                    CannedResponse.shortcode.ilike(search_term),
                )
            )

        return query.order_by(CannedResponse.name.asc()).all()

    def get(self, response_id: int) -> CannedResponse:
        """Get a canned response by ID.

        Args:
            response_id: The canned response ID.

        Returns:
            CannedResponse instance.

        Raises:
            CannedResponseNotFoundError: If not found.
        """
        response = (
            self.db.query(CannedResponse)
            .filter(CannedResponse.id == response_id)
            .first()
        )
        if not response:
            raise CannedResponseNotFoundError(response_id)
        return response

    def get_by_shortcode(
        self,
        shortcode: str,
        agent_id: Optional[int] = None,
    ) -> Optional[CannedResponse]:
        """Get a canned response by shortcode.

        Args:
            shortcode: The shortcode (e.g., /greeting).
            agent_id: Optional agent ID for scope filtering.

        Returns:
            CannedResponse instance or None.
        """
        query = self.db.query(CannedResponse).filter(
            CannedResponse.shortcode == shortcode,
            CannedResponse.is_active == True,
        )

        if agent_id:
            # Get agent's teams
            team_ids = (
                self.db.query(TeamMember.team_id)
                .filter(
                    TeamMember.agent_id == agent_id,
                    TeamMember.is_active == True,
                )
                .all()
            )
            team_ids = [t[0] for t in team_ids]

            # Filter by accessible scopes
            query = query.filter(
                or_(
                    CannedResponse.scope == CannedResponseScope.GLOBAL.value,
                    (CannedResponse.scope == CannedResponseScope.PERSONAL.value)
                    & (CannedResponse.agent_id == agent_id),
                    (CannedResponse.scope == CannedResponseScope.TEAM.value)
                    & (CannedResponse.team_id.in_(team_ids)),
                )
            )

        return query.first()

    def get_available_for_agent(self, agent_id: int) -> List[CannedResponse]:
        """Get all canned responses available to an agent.

        This includes:
        - Personal responses owned by the agent
        - Team responses for teams the agent belongs to
        - Global responses

        Args:
            agent_id: The agent ID.

        Returns:
            List of CannedResponse instances.
        """
        # Get agent's teams
        team_ids = (
            self.db.query(TeamMember.team_id)
            .filter(
                TeamMember.agent_id == agent_id,
                TeamMember.is_active == True,
            )
            .all()
        )
        team_ids = [t[0] for t in team_ids]

        query = self.db.query(CannedResponse).filter(
            CannedResponse.is_active == True,
            or_(
                CannedResponse.scope == CannedResponseScope.GLOBAL.value,
                (CannedResponse.scope == CannedResponseScope.PERSONAL.value)
                & (CannedResponse.agent_id == agent_id),
                (CannedResponse.scope == CannedResponseScope.TEAM.value)
                & (CannedResponse.team_id.in_(team_ids)),
            ),
        )

        return query.order_by(CannedResponse.name.asc()).all()

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create(self, data: CannedResponseCreate) -> CannedResponse:
        """Create a new canned response.

        Args:
            data: Creation data.

        Returns:
            Created CannedResponse instance.

        Raises:
            DuplicateShortcodeError: If shortcode already exists.
        """
        # Check for duplicate shortcode
        if data.shortcode:
            existing = (
                self.db.query(CannedResponse)
                .filter(CannedResponse.shortcode == data.shortcode)
                .first()
            )
            if existing:
                raise DuplicateShortcodeError(data.shortcode)

        response = CannedResponse(
            name=data.name,
            content=data.content,
            shortcode=data.shortcode,
            scope=data.scope,
            team_id=data.team_id,
            agent_id=data.agent_id,
            category=data.category,
            usage_count=0,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Set created_by if principal available
        if self.principal:
            response.created_by_id = getattr(self.principal, "id", None)

        self.db.add(response)
        self.db.flush()
        return response

    def update(
        self,
        response_id: int,
        data: CannedResponseUpdate,
    ) -> CannedResponse:
        """Update a canned response.

        Args:
            response_id: The canned response ID.
            data: Update data.

        Returns:
            Updated CannedResponse instance.

        Raises:
            CannedResponseNotFoundError: If not found.
            DuplicateShortcodeError: If new shortcode conflicts.
        """
        response = self.get(response_id)

        if data.shortcode is not None and data.shortcode != response.shortcode:
            if data.shortcode:
                existing = (
                    self.db.query(CannedResponse)
                    .filter(
                        CannedResponse.shortcode == data.shortcode,
                        CannedResponse.id != response_id,
                    )
                    .first()
                )
                if existing:
                    raise DuplicateShortcodeError(data.shortcode)
            response.shortcode = data.shortcode

        if data.name is not None:
            response.name = data.name

        if data.content is not None:
            response.content = data.content

        if data.scope is not None:
            response.scope = data.scope

        if data.team_id is not None:
            response.team_id = data.team_id

        if data.category is not None:
            response.category = data.category

        if data.is_active is not None:
            response.is_active = data.is_active

        response.updated_at = datetime.now(timezone.utc)

        # Set updated_by if principal available
        if self.principal:
            response.updated_by_id = getattr(self.principal, "id", None)

        self.db.flush()
        return response

    def delete(self, response_id: int) -> bool:
        """Delete a canned response.

        Args:
            response_id: The canned response ID.

        Returns:
            True if deleted.

        Raises:
            CannedResponseNotFoundError: If not found.
        """
        response = self.get(response_id)
        self.db.delete(response)
        self.db.flush()
        return True

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def render(
        self,
        response_id: int,
        variables: Optional[Dict[str, str]] = None,
        ticket: Optional[Ticket] = None,
        conversation: Optional[OmniConversation] = None,
        agent: Optional[Agent] = None,
    ) -> str:
        """Render a canned response with variable substitution.

        Args:
            response_id: The canned response ID.
            variables: Optional custom variables dict.
            ticket: Optional Ticket for extracting context.
            conversation: Optional OmniConversation for context.
            agent: Optional Agent for context.

        Returns:
            Rendered content string.
        """
        response = self.get(response_id)
        return self._render_content(
            response.content,
            variables=variables,
            ticket=ticket,
            conversation=conversation,
            agent=agent,
        )

    def render_content(
        self,
        content: str,
        variables: Optional[Dict[str, str]] = None,
        ticket: Optional[Ticket] = None,
        conversation: Optional[OmniConversation] = None,
        agent: Optional[Agent] = None,
    ) -> str:
        """Render arbitrary content with variable substitution.

        Args:
            content: The template content.
            variables: Optional custom variables dict.
            ticket: Optional Ticket for extracting context.
            conversation: Optional OmniConversation for context.
            agent: Optional Agent for context.

        Returns:
            Rendered content string.
        """
        return self._render_content(
            content,
            variables=variables,
            ticket=ticket,
            conversation=conversation,
            agent=agent,
        )

    def _render_content(
        self,
        content: str,
        variables: Optional[Dict[str, str]] = None,
        ticket: Optional[Ticket] = None,
        conversation: Optional[OmniConversation] = None,
        agent: Optional[Agent] = None,
    ) -> str:
        """Internal render implementation."""
        # Build context from provided objects
        context: Dict[str, Any] = {}

        # Add datetime variables
        now = datetime.now(timezone.utc)
        context["date"] = now.strftime("%Y-%m-%d")
        context["time"] = now.strftime("%H:%M")
        context["datetime"] = now.strftime("%Y-%m-%d %H:%M")

        # Add ticket context
        if ticket:
            context["ticket.number"] = getattr(ticket, "number", "") or ""
            context["ticket.subject"] = getattr(ticket, "subject", "") or ""
            context["ticket.status"] = getattr(ticket, "status", "") or ""
            if hasattr(ticket, "status") and ticket.status:
                context["ticket.status"] = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
            context["ticket.priority"] = ""
            if hasattr(ticket, "priority") and ticket.priority:
                context["ticket.priority"] = ticket.priority.value if hasattr(ticket.priority, "value") else str(ticket.priority)

            # Customer from ticket
            if hasattr(ticket, "customer") and ticket.customer:
                context["customer.name"] = getattr(ticket.customer, "name", "") or ""
                context["customer.email"] = getattr(ticket.customer, "email", "") or ""
                context["customer.company"] = getattr(ticket.customer, "company_name", "") or ""

        # Add conversation context
        if conversation:
            context["conversation.subject"] = getattr(conversation, "subject", "") or ""
            context["conversation.channel"] = ""
            if hasattr(conversation, "channel") and conversation.channel:
                context["conversation.channel"] = getattr(conversation.channel, "name", "") or ""

            # Customer from conversation
            context.setdefault("customer.name", getattr(conversation, "contact_name", "") or "")
            context.setdefault("customer.email", getattr(conversation, "contact_email", "") or "")
            context.setdefault("customer.company", getattr(conversation, "contact_company", "") or "")

        # Add agent context
        if agent:
            context["agent.name"] = getattr(agent, "display_name", "") or ""
            context["agent.email"] = getattr(agent, "email", "") or ""

        # Override with explicit variables
        if variables:
            context.update(variables)

        # Replace placeholders
        result = content
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            result = result.replace(placeholder, str(value))

        return result

    def get_supported_variables(self) -> List[str]:
        """Return list of supported placeholder variables.

        Returns:
            List of variable names.
        """
        return list(SUPPORTED_VARIABLES)

    def extract_variables(self, content: str) -> List[str]:
        """Extract placeholder variables from content.

        Args:
            content: The template content.

        Returns:
            List of variable names found in content.
        """
        pattern = r"\{\{([^}]+)\}\}"
        matches = re.findall(pattern, content)
        return list(set(matches))

    # -------------------------------------------------------------------------
    # Usage Tracking
    # -------------------------------------------------------------------------

    def record_usage(self, response_id: int) -> None:
        """Record usage of a canned response.

        Args:
            response_id: The canned response ID.
        """
        response = self.get(response_id)
        response.usage_count = (response.usage_count or 0) + 1
        response.last_used_at = datetime.now(timezone.utc)
        self.db.flush()

    def get_most_used(self, limit: int = 10) -> List[CannedResponse]:
        """Get most frequently used canned responses.

        Args:
            limit: Maximum number of results.

        Returns:
            List of CannedResponse instances ordered by usage.
        """
        return (
            self.db.query(CannedResponse)
            .filter(CannedResponse.is_active == True)
            .order_by(CannedResponse.usage_count.desc())
            .limit(limit)
            .all()
        )

    def get_categories(self) -> List[str]:
        """Get all unique categories.

        Returns:
            List of category names.
        """
        results = (
            self.db.query(CannedResponse.category)
            .filter(
                CannedResponse.is_active == True,
                CannedResponse.category.isnot(None),
            )
            .distinct()
            .all()
        )
        return sorted([r[0] for r in results if r[0]])
