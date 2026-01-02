"""Module auto-discovery and registration.

This module provides the central ModuleRegistry that:
1. Auto-discovers modules in app/modules/
2. Registers their routers, configs, and navigation
3. Provides permission-filtered access to navigation and module lists

Usage:
    from app.web.modules import ModuleRegistry

    # At app startup
    ModuleRegistry.discover_modules()

    # Get routers for FastAPI
    for router in ModuleRegistry.get_all_routers():
        app.include_router(router)

    # Get navigation for templates
    nav = ModuleRegistry.get_navigation(user_scopes)
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from .module_types import (
    ModuleConfig,
    NavigationSection,
    RegisteredModule,
    navigation_from_dict,
)

__all__ = ["ModuleRegistry"]

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Central registry for all web modules.

    This is a class with class methods (not instance methods) to act
    as a singleton registry accessible from anywhere in the application.
    """

    _modules: Dict[str, RegisteredModule] = {}
    _discovered: bool = False

    @classmethod
    def reset(cls) -> None:
        """Reset the registry (useful for testing)."""
        cls._modules = {}
        cls._discovered = False

    @classmethod
    def discover_modules(cls, force: bool = False) -> int:
        """Auto-discover and register all modules in app/modules/.

        Modules must export:
        - MODULE_CONFIG: ModuleConfig instance
        - router: FastAPI APIRouter instance
        - NAVIGATION: Optional list of navigation sections (dict format)

        Args:
            force: If True, rediscover even if already discovered.

        Returns:
            Number of modules discovered.
        """
        if cls._discovered and not force:
            return len(cls._modules)

        import app.modules as modules_pkg

        discovered_count = 0

        for finder, name, ispkg in pkgutil.iter_modules(modules_pkg.__path__):
            if not ispkg:
                continue

            try:
                module = importlib.import_module(f"app.modules.{name}")

                # Check for required exports
                if not hasattr(module, "MODULE_CONFIG"):
                    logger.debug(f"Module {name} missing MODULE_CONFIG, skipping")
                    continue

                if not hasattr(module, "router"):
                    logger.debug(f"Module {name} missing router, skipping")
                    continue

                config = module.MODULE_CONFIG
                if not isinstance(config, ModuleConfig):
                    logger.warning(
                        f"Module {name} MODULE_CONFIG is not a ModuleConfig instance"
                    )
                    continue

                router = module.router
                if not isinstance(router, APIRouter):
                    logger.warning(f"Module {name} router is not an APIRouter instance")
                    continue

                # Get optional navigation (can be dict or NavigationSection list)
                raw_nav = getattr(module, "NAVIGATION", [])
                if raw_nav and isinstance(raw_nav[0], dict):
                    navigation = navigation_from_dict(raw_nav)
                else:
                    navigation = raw_nav

                cls.register(config, router, navigation)
                discovered_count += 1
                logger.info(f"Discovered module: {name} ({config.name})")

            except ImportError as e:
                logger.debug(f"Could not import module {name}: {e}")
            except Exception as e:
                logger.warning(f"Error loading module {name}: {e}")

        cls._discovered = True
        logger.info(f"Module discovery complete: {discovered_count} modules registered")
        return discovered_count

    @classmethod
    def register(
        cls,
        config: ModuleConfig,
        router: APIRouter,
        navigation: Optional[List[NavigationSection]] = None,
    ) -> None:
        """Register a module manually.

        Args:
            config: Module configuration.
            router: FastAPI router for this module.
            navigation: Optional navigation sections.
        """
        if config.id in cls._modules:
            logger.warning(f"Module {config.id} already registered, replacing")

        cls._modules[config.id] = RegisteredModule(
            config=config,
            router=router,
            navigation=navigation or [],
        )

    @classmethod
    def get(cls, module_id: str) -> Optional[RegisteredModule]:
        """Get a registered module by ID."""
        return cls._modules.get(module_id)

    @classmethod
    def get_all(cls) -> List[RegisteredModule]:
        """Get all registered modules."""
        return list(cls._modules.values())

    @classmethod
    def get_all_routers(cls) -> List[APIRouter]:
        """Get all module routers for inclusion in main app.

        Only returns routers for enabled modules.
        """
        return [m.router for m in cls._modules.values() if m.enabled]

    @classmethod
    def get_module_registry(
        cls, user_scopes: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get module switcher items filtered by user permissions.

        Args:
            user_scopes: List of permission scopes the user has.

        Returns:
            List of module dicts for the module switcher UI.
        """
        user_scopes = user_scopes or []
        modules = []

        for module in sorted(
            cls._modules.values(),
            key=lambda m: (m.config.group, m.config.order, m.config.name),
        ):
            if not module.enabled:
                continue

            if not module.config.user_has_access(user_scopes):
                continue

            modules.append(module.config.to_dict())

        return modules

    @classmethod
    def get_navigation(
        cls,
        user_scopes: Optional[List[str]] = None,
        active_module_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Build navigation filtered by user permissions.

        Args:
            user_scopes: List of permission scopes the user has.
            active_module_id: Currently active module ID (for filtering).

        Returns:
            List of navigation sections for the sidebar.
        """
        user_scopes = user_scopes or []
        navigation = []

        for module in sorted(
            cls._modules.values(),
            key=lambda m: (m.config.group, m.config.order),
        ):
            if not module.enabled:
                continue

            # If active_module_id is set, only include that module's navigation
            # (unless it's a "global" module which would be handled separately)
            if active_module_id and module.id != active_module_id:
                continue

            for section in sorted(module.navigation, key=lambda s: s.order):
                # Check section-level permission
                if section.scope and section.scope not in user_scopes:
                    continue

                # Filter links by permission
                filtered_links = []
                for link in section.links:
                    if link.scope and link.scope not in user_scopes:
                        continue
                    filtered_links.append({
                        "label": link.label,
                        "href": link.href,
                        "icon": link.icon,
                        "badge": link.badge,
                    })

                # Only include section if it has visible links
                if filtered_links:
                    navigation.append({
                        "section": section.section,
                        "href": section.href,
                        "icon": section.icon,
                        "module": module.id,
                        "links": filtered_links,
                    })

        return navigation

    @classmethod
    def get_active_module(cls, path: str) -> Optional[Dict[str, Any]]:
        """Get the active module based on the current URL path.

        Args:
            path: Current URL path (e.g., "/sales/quotations/123").

        Returns:
            Module dict if found, None otherwise.
        """
        for module in cls._modules.values():
            if module.config.matches_path(path):
                return module.config.to_dict()
        return None

    @classmethod
    def get_active_module_id(cls, path: str) -> Optional[str]:
        """Get the active module ID based on the current URL path.

        Args:
            path: Current URL path.

        Returns:
            Module ID if found, None otherwise.
        """
        for module in cls._modules.values():
            if module.config.matches_path(path):
                return module.id
        return None
