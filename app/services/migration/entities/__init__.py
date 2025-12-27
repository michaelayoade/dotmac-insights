"""Migration entity definitions.

This package contains entity configurations organized by module.
"""
from .base import FieldType, FieldConfig, EntityConfig
from .core import CORE_ENTITIES
from .accounting import ACCOUNTING_ENTITIES
from .sales import SALES_ENTITIES
from .purchasing import PURCHASING_ENTITIES
from .hr import HR_ENTITIES
from .tax import TAX_ENTITIES
from .crm import CRM_ENTITIES
from .support import SUPPORT_ENTITIES
from .inventory import INVENTORY_ENTITIES
from .projects import PROJECT_ENTITIES
from .assets import ASSET_ENTITIES
from .expenses import EXPENSE_ENTITIES

# Combined registry of all entities
ENTITY_REGISTRY: dict[str, EntityConfig] = {
    **CORE_ENTITIES,
    **ACCOUNTING_ENTITIES,
    **SALES_ENTITIES,
    **PURCHASING_ENTITIES,
    **HR_ENTITIES,
    **TAX_ENTITIES,
    **CRM_ENTITIES,
    **SUPPORT_ENTITIES,
    **INVENTORY_ENTITIES,
    **PROJECT_ENTITIES,
    **ASSET_ENTITIES,
    **EXPENSE_ENTITIES,
}

__all__ = [
    "FieldType",
    "FieldConfig",
    "EntityConfig",
    "ENTITY_REGISTRY",
    "CORE_ENTITIES",
    "ACCOUNTING_ENTITIES",
    "SALES_ENTITIES",
    "PURCHASING_ENTITIES",
    "HR_ENTITIES",
    "TAX_ENTITIES",
    "CRM_ENTITIES",
    "SUPPORT_ENTITIES",
    "INVENTORY_ENTITIES",
    "PROJECT_ENTITIES",
    "ASSET_ENTITIES",
    "EXPENSE_ENTITIES",
]
