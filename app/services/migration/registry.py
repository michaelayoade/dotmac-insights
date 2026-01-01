"""Entity registry for data migration.

Defines all importable entities with their schemas, required fields,
unique fields for deduplication, and foreign key dependencies.

This module re-exports the ENTITY_REGISTRY from the entities package
and provides helper functions for working with entities.
"""
from __future__ import annotations

from typing import Any

from app.models.migration import EntityType

# Import types and registry from entities package
from .entities import (
    FieldType,
    FieldConfig,
    EntityConfig,
    ENTITY_REGISTRY,
)


def get_entity_config(entity_type: str | EntityType) -> EntityConfig | None:
    """Get entity configuration by type.

    Args:
        entity_type: Entity type string or EntityType enum

    Returns:
        EntityConfig dict or None if not found
    """
    if isinstance(entity_type, EntityType):
        entity_type = entity_type.value
    return ENTITY_REGISTRY.get(entity_type)


def get_entity_fields(entity_type: str | EntityType) -> dict[str, FieldConfig]:
    """Get field definitions for an entity.

    Args:
        entity_type: Entity type string or EntityType enum

    Returns:
        Dict of field name -> FieldConfig
    """
    config = get_entity_config(entity_type)
    if config:
        return config.get("fields", {})
    return {}


def get_required_fields(entity_type: str | EntityType) -> list[str]:
    """Get required fields for an entity.

    Args:
        entity_type: Entity type string or EntityType enum

    Returns:
        List of required field names
    """
    config = get_entity_config(entity_type)
    if config:
        return config.get("required_fields", [])
    return []


def get_unique_fields(entity_type: str | EntityType) -> list[str]:
    """Get unique/dedup fields for an entity.

    Args:
        entity_type: Entity type string or EntityType enum

    Returns:
        List of unique field names
    """
    config = get_entity_config(entity_type)
    if config:
        return config.get("unique_fields", [])
    return []


def get_lookup_fields(entity_type: str | EntityType) -> list[str]:
    """Get lookup fields for an entity (for FK resolution).

    Args:
        entity_type: Entity type string or EntityType enum

    Returns:
        List of lookup field names
    """
    config = get_entity_config(entity_type)
    if config:
        return config.get("lookup_fields", [])
    return []


def list_entities() -> list[dict]:
    """List all available entities with basic info.

    Returns:
        List of entity info dicts
    """
    return [
        {
            "type": entity_type,
            "display_name": config.get("display_name", entity_type),
            "description": config.get("description", ""),
            "required_fields": config.get("required_fields", []),
            "unique_fields": config.get("unique_fields", []),
            "dependencies": config.get("dependencies", []),
        }
        for entity_type, config in ENTITY_REGISTRY.items()
    ]


def get_dependencies(entity_type: str | EntityType) -> list[str]:
    """Get dependencies for an entity.

    Args:
        entity_type: Entity type string or EntityType enum

    Returns:
        List of dependency entity type names
    """
    config = get_entity_config(entity_type)
    if config:
        return config.get("dependencies", [])
    return []


def get_migration_order() -> list[str]:
    """Get recommended migration order based on dependencies.

    Uses topological sort to order entities so that dependencies
    are migrated before dependent entities.

    Returns:
        List of entity types in recommended migration order
    """
    # Build dependency graph
    graph: dict[str, list[str]] = {}
    in_degree: dict[str, int] = {}

    for entity_type in ENTITY_REGISTRY:
        config = ENTITY_REGISTRY[entity_type]
        deps = config.get("dependencies", [])
        graph[entity_type] = deps
        in_degree[entity_type] = len(deps)

    # Topological sort (Kahn's algorithm)
    result = []
    queue = [e for e in in_degree if in_degree[e] == 0]

    while queue:
        # Sort for deterministic order
        queue.sort()
        current = queue.pop(0)
        result.append(current)

        # Find all entities that depend on current
        for entity_type, deps in graph.items():
            if current in deps:
                in_degree[entity_type] -= 1
                if in_degree[entity_type] == 0:
                    queue.append(entity_type)

    # Check for circular dependencies
    if len(result) != len(ENTITY_REGISTRY):
        # There are circular dependencies - just append remaining
        for entity_type in ENTITY_REGISTRY:
            if entity_type not in result:
                result.append(entity_type)

    return result


def check_dependencies_migrated(
    entity_type: str,
    migrated_entities: set[str]
) -> tuple[bool, list[str]]:
    """Check if all dependencies for an entity have been migrated.

    Args:
        entity_type: Entity type to check
        migrated_entities: Set of already migrated entity types

    Returns:
        Tuple of (all_satisfied, missing_dependencies)
    """
    dependencies = get_dependencies(entity_type)
    missing = [dep for dep in dependencies if dep not in migrated_entities]
    return len(missing) == 0, missing


def get_fk_fields(entity_type: str) -> dict[str, dict]:
    """Get all foreign key fields for an entity.

    Args:
        entity_type: Entity type

    Returns:
        Dict of field_name -> {fk_entity, fk_lookup_fields, required}
    """
    fields = get_entity_fields(entity_type)
    fk_fields = {}

    for name, cfg in fields.items():
        if cfg.get("type") == FieldType.FOREIGN_KEY:
            fk_fields[name] = {
                "fk_entity": cfg.get("fk_entity"),
                "fk_lookup_fields": cfg.get("fk_lookup_fields", ["id"]),
                "required": cfg.get("required", False),
            }

    return fk_fields


# Re-export for backwards compatibility
__all__ = [
    "FieldType",
    "FieldConfig",
    "EntityConfig",
    "ENTITY_REGISTRY",
    "get_entity_config",
    "get_entity_fields",
    "get_required_fields",
    "get_unique_fields",
    "get_lookup_fields",
    "list_entities",
    "get_dependencies",
    "get_migration_order",
    "check_dependencies_migrated",
    "get_fk_fields",
]
