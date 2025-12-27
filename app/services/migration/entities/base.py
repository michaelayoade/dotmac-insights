"""Base types for migration entity definitions."""
from __future__ import annotations

from typing import Any, TypedDict, Optional
from enum import Enum


class FieldType(str, Enum):
    """Field data types for validation."""
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    PHONE = "phone"
    JSON = "json"
    ENUM = "enum"
    FOREIGN_KEY = "foreign_key"


class FieldConfig(TypedDict, total=False):
    """Configuration for a single field."""
    type: FieldType
    required: bool
    unique: bool
    max_length: Optional[int]
    enum_values: Optional[list[str]]
    default: Any
    description: str
    # For foreign keys
    fk_entity: Optional[str]
    fk_lookup_fields: Optional[list[str]]
    # For cleaning
    normalizer: Optional[str]  # phone, email, name, address, currency, date


class EntityConfig(TypedDict, total=False):
    """Configuration for an importable entity."""
    model_name: str
    display_name: str
    description: str
    fields: dict[str, FieldConfig]
    required_fields: list[str]
    unique_fields: list[str]
    lookup_fields: list[str]  # Fields that can be used to lookup existing records
    dependencies: list[str]  # Other entities that must exist first
    supports_upsert: bool
    supports_rollback: bool
