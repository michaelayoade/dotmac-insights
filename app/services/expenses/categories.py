"""Expense category service - business logic for expense category management.

This service encapsulates all expense category-related business logic:
- Category CRUD operations
- Hierarchy management
- Duplicate name checking

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import or_, desc, asc
from sqlalchemy.orm import Session

from app.models.expense_management import ExpenseCategory

from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ExpenseCategoryService"]


class ExpenseCategoryService:
    """Service for expense category business logic.

    Handles category CRUD operations and hierarchy management.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list_categories(
        self,
        search: Optional[str] = None,
        is_active: Optional[bool] = True,
        is_group: Optional[bool] = None,
        company: Optional[str] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[ExpenseCategory]:
        """List expense categories with optional filtering.

        Args:
            search: Optional search term for name/code.
            is_active: Filter by active status (default True).
            is_group: Filter by group status.
            company: Filter by company.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing categories and total count.
        """
        pagination = pagination or PaginationParams()

        query = self.db.query(ExpenseCategory)

        # Active filter
        if is_active is not None:
            query = query.filter(ExpenseCategory.is_active == is_active)

        # Search
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    ExpenseCategory.name.ilike(search_term),
                    ExpenseCategory.code.ilike(search_term),
                    ExpenseCategory.description.ilike(search_term),
                )
            )

        # Filters
        if is_group is not None:
            query = query.filter(ExpenseCategory.is_group == is_group)
        if company:
            query = query.filter(
                or_(
                    ExpenseCategory.company == company,
                    ExpenseCategory.company.is_(None),  # Include global categories
                )
            )

        # Count total
        total = query.count()

        # Sorting (alphabetically by name)
        query = query.order_by(asc(ExpenseCategory.name))

        # Pagination
        query = query.offset(pagination.offset).limit(pagination.limit)

        return PaginatedResult(
            items=query.all(),
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get_category(self, category_id: int) -> ExpenseCategory:
        """Get a single expense category by ID.

        Args:
            category_id: The category ID.

        Returns:
            The ExpenseCategory object.

        Raises:
            NotFoundError: If category not found.
        """
        category = (
            self.db.query(ExpenseCategory)
            .filter(ExpenseCategory.id == category_id)
            .first()
        )
        if not category:
            raise NotFoundError(f"Expense category {category_id} not found")
        return category

    def get_category_by_code(self, code: str) -> Optional[ExpenseCategory]:
        """Get an expense category by code.

        Args:
            code: The category code.

        Returns:
            The ExpenseCategory object or None if not found.
        """
        return (
            self.db.query(ExpenseCategory)
            .filter(ExpenseCategory.code == code)
            .first()
        )

    def check_name_exists(
        self, name: str, exclude_id: Optional[int] = None
    ) -> bool:
        """Check if a category with the given name already exists.

        Args:
            name: The category name to check.
            exclude_id: Optional category ID to exclude from check.

        Returns:
            True if a category with the name exists, False otherwise.
        """
        query = self.db.query(ExpenseCategory).filter(
            ExpenseCategory.name == name,
            ExpenseCategory.is_active == True,
        )
        if exclude_id:
            query = query.filter(ExpenseCategory.id != exclude_id)
        return query.first() is not None

    def check_code_exists(
        self, code: str, exclude_id: Optional[int] = None
    ) -> bool:
        """Check if a category with the given code already exists.

        Args:
            code: The category code to check.
            exclude_id: Optional category ID to exclude from check.

        Returns:
            True if a category with the code exists, False otherwise.
        """
        query = self.db.query(ExpenseCategory).filter(ExpenseCategory.code == code)
        if exclude_id:
            query = query.filter(ExpenseCategory.id != exclude_id)
        return query.first() is not None

    def get_leaf_categories(self) -> List[ExpenseCategory]:
        """Get all non-group (leaf) categories.

        Returns:
            List of categories that are not groups.
        """
        return (
            self.db.query(ExpenseCategory)
            .filter(
                ExpenseCategory.is_group == False,
                ExpenseCategory.is_active == True,
            )
            .order_by(ExpenseCategory.name)
            .all()
        )

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create_category(
        self,
        name: str,
        code: str,
        expense_account: str,
        description: Optional[str] = None,
        parent_id: Optional[int] = None,
        is_group: bool = False,
        payable_account: Optional[str] = None,
        category_type: Optional[str] = None,
        default_tax_code_id: Optional[int] = None,
        is_tax_deductible: bool = True,
        requires_receipt: bool = True,
        company: Optional[str] = None,
    ) -> ExpenseCategory:
        """Create a new expense category.

        Args:
            name: Category name.
            code: Unique category code.
            expense_account: Default GL expense account.
            description: Optional description.
            parent_id: Optional parent category ID.
            is_group: Whether this is a group category.
            payable_account: Optional override AP account.
            category_type: Optional category type.
            default_tax_code_id: Optional default tax code.
            is_tax_deductible: Whether expenses are tax deductible.
            requires_receipt: Whether receipts are required.
            company: Optional company scope.

        Returns:
            The created ExpenseCategory.

        Raises:
            ValidationError: If validation fails.
            ConflictError: If category name or code already exists.
        """
        if not name:
            raise ValidationError("Category name is required")
        if not code:
            raise ValidationError("Category code is required")
        if not expense_account:
            raise ValidationError("Expense account is required")

        # Check for duplicate name
        if self.check_name_exists(name):
            raise ConflictError(f"Category with name '{name}' already exists")

        # Check for duplicate code
        if self.check_code_exists(code):
            raise ConflictError(f"Category with code '{code}' already exists")

        # Validate parent if specified
        if parent_id:
            parent = self.get_category(parent_id)
            if not parent.is_group:
                raise ValidationError(
                    f"Parent category '{parent.name}' is not a group category"
                )

        category = ExpenseCategory(
            name=name,
            code=code,
            expense_account=expense_account,
            description=description,
            parent_id=parent_id,
            is_group=is_group,
            payable_account=payable_account,
            category_type=category_type,
            default_tax_code_id=default_tax_code_id,
            is_tax_deductible=is_tax_deductible,
            requires_receipt=requires_receipt,
            company=company,
            is_active=True,
            is_system=False,
        )

        self.db.add(category)
        self.db.flush()

        return category

    def update_category(
        self,
        category_id: int,
        name: Optional[str] = None,
        code: Optional[str] = None,
        expense_account: Optional[str] = None,
        description: Optional[str] = None,
        parent_id: Optional[int] = None,
        is_group: Optional[bool] = None,
        payable_account: Optional[str] = None,
        category_type: Optional[str] = None,
        default_tax_code_id: Optional[int] = None,
        is_tax_deductible: Optional[bool] = None,
        requires_receipt: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ) -> ExpenseCategory:
        """Update an existing expense category.

        Args:
            category_id: The category ID.
            Other args: Optional fields to update.

        Returns:
            The updated ExpenseCategory.

        Raises:
            NotFoundError: If category not found.
            ValidationError: If validation fails or category is system.
            ConflictError: If new name/code conflicts.
        """
        category = self.get_category(category_id)

        if category.is_system:
            raise ValidationError("System categories cannot be modified")

        # Check name change for conflict
        if name and name != category.name:
            if self.check_name_exists(name, exclude_id=category_id):
                raise ConflictError(f"Category with name '{name}' already exists")
            category.name = name

        # Check code change for conflict
        if code and code != category.code:
            if self.check_code_exists(code, exclude_id=category_id):
                raise ConflictError(f"Category with code '{code}' already exists")
            category.code = code

        # Update other fields
        if expense_account is not None:
            category.expense_account = expense_account
        if description is not None:
            category.description = description
        if parent_id is not None:
            if parent_id:
                parent = self.get_category(parent_id)
                if not parent.is_group:
                    raise ValidationError(
                        f"Parent category '{parent.name}' is not a group category"
                    )
                if parent_id == category_id:
                    raise ValidationError("Category cannot be its own parent")
            category.parent_id = parent_id or None
        if is_group is not None:
            category.is_group = is_group
        if payable_account is not None:
            category.payable_account = payable_account or None
        if category_type is not None:
            category.category_type = category_type or None
        if default_tax_code_id is not None:
            category.default_tax_code_id = default_tax_code_id or None
        if is_tax_deductible is not None:
            category.is_tax_deductible = is_tax_deductible
        if requires_receipt is not None:
            category.requires_receipt = requires_receipt
        if is_active is not None:
            category.is_active = is_active

        self.db.flush()

        return category

    def delete_category(self, category_id: int) -> None:
        """Soft delete an expense category (deactivate).

        System categories cannot be deleted.

        Args:
            category_id: The category ID.

        Raises:
            NotFoundError: If category not found.
            ValidationError: If category is a system category.
        """
        category = self.get_category(category_id)

        if category.is_system:
            raise ValidationError("System categories cannot be deleted")

        # Check for children
        children = (
            self.db.query(ExpenseCategory)
            .filter(
                ExpenseCategory.parent_id == category_id,
                ExpenseCategory.is_active == True,
            )
            .first()
        )
        if children:
            raise ValidationError(
                "Cannot delete category with active child categories"
            )

        category.is_active = False
        self.db.flush()
