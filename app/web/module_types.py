"""Module type definitions for the modular app system.

This module defines the standard interface for web modules, enabling
auto-discovery and consistent configuration across all modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

__all__ = [
    "ModuleConfig",
    "NavigationSection",
    "NavigationLink",
    "RegisteredModule",
]


@dataclass(frozen=True)
class NavigationLink:
    """A single navigation link within a section."""

    label: str
    href: str
    icon: str = "circle"
    scope: Optional[str] = None  # Required permission scope
    badge: Optional[str] = None  # Optional badge text (e.g., "New", "Beta")


@dataclass(frozen=True)
class NavigationSection:
    """A navigation section containing multiple links."""

    section: str  # Section title
    href: str  # Section header link
    icon: str  # Section icon
    links: List[NavigationLink] = field(default_factory=list)
    scope: Optional[str] = None  # Required permission scope for entire section
    order: int = 100  # Sort order within module


@dataclass(frozen=True)
class ModuleConfig:
    """Standard module configuration.

    Every module must export a MODULE_CONFIG instance of this class
    to participate in auto-discovery.

    Example:
        MODULE_CONFIG = ModuleConfig(
            id="sales",
            name="Sales",
            description="Manage quotations, orders, and revenue",
            icon="shopping-cart",
            prefix="/sales",
            group="Back Office",
            order=10,
            scopes=["sales:read"],
        )
    """

    id: str  # Unique identifier (e.g., "sales", "accounting")
    name: str  # Display name (e.g., "Sales", "Accounting")
    description: str  # Short description for tooltips/help
    icon: str  # Icon name from the icon set
    prefix: str  # URL prefix (e.g., "/sales")
    group: str  # Navigation group (e.g., "Back Office", "Operations")
    order: int = 100  # Sort order within group
    scopes: List[str] = field(default_factory=list)  # Required permission scopes
    enabled: bool = True  # Can be disabled via settings
    prefixes: List[str] = field(default_factory=list)  # Additional URL prefixes for matching

    def __post_init__(self) -> None:
        """Ensure prefixes includes the main prefix."""
        if self.prefix and self.prefix not in self.prefixes:
            # Since frozen, we need to use object.__setattr__
            object.__setattr__(self, "prefixes", [self.prefix] + list(self.prefixes))

    def matches_path(self, path: str) -> bool:
        """Check if a URL path belongs to this module."""
        return any(path.startswith(prefix) for prefix in self.prefixes)

    def user_has_access(self, user_scopes: List[str]) -> bool:
        """Check if user has access to this module."""
        if not self.scopes:
            return True
        return any(scope in user_scopes for scope in self.scopes)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for template rendering."""
        return {
            "id": self.id,
            "name": self.name,
            "label": self.name,  # Alias for compatibility
            "description": self.description,
            "icon": self.icon,
            "href": self.prefix,
            "group": self.group,
            "order": self.order,
            "scopes": self.scopes,
            "prefixes": self.prefixes,
        }


@dataclass
class RegisteredModule:
    """A module registered with the ModuleRegistry."""

    config: ModuleConfig
    router: APIRouter
    navigation: List[NavigationSection] = field(default_factory=list)

    @property
    def id(self) -> str:
        """Module ID shortcut."""
        return self.config.id

    @property
    def enabled(self) -> bool:
        """Module enabled shortcut."""
        return self.config.enabled


def navigation_from_dict(data: List[Dict]) -> List[NavigationSection]:
    """Convert navigation dict format to typed NavigationSection list.

    This helper allows modules to define navigation as simple dicts
    while still getting type safety in the registry.

    Example input:
        [
            {
                "section": "Sales",
                "href": "/sales",
                "icon": "shopping-cart",
                "scope": "sales:read",
                "links": [
                    {"label": "Dashboard", "href": "/sales", "icon": "home"},
                    {"label": "Quotations", "href": "/sales/quotations", "icon": "file-text"},
                ],
            },
        ]
    """
    sections = []
    for section_data in data:
        links = [
            NavigationLink(
                label=link.get("label", ""),
                href=link.get("href", ""),
                icon=link.get("icon", "circle"),
                scope=link.get("scope"),
                badge=link.get("badge"),
            )
            for link in section_data.get("links", [])
        ]
        sections.append(
            NavigationSection(
                section=section_data.get("section", ""),
                href=section_data.get("href", ""),
                icon=section_data.get("icon", "folder"),
                links=links,
                scope=section_data.get("scope"),
                order=section_data.get("order", 100),
            )
        )
    return sections
