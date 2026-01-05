"""Serial number service - business logic for serial number tracking and management.

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import or_, desc, asc
from sqlalchemy.orm import Session

from app.models.inventory import SerialNumber, SerialStatus
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams
from app.services.validation.soft_validation_service import SoftValidationService

from .types import SerialFilters, SerialCreateData

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["SerialService"]


class SerialService:
    """Service for serial number tracking business logic.

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

    def list_serials(
        self,
        filters: Optional[SerialFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[SerialNumber]:
        """List serial numbers with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing serial numbers and total count.
        """
        if filters is None:
            filters = SerialFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(SerialNumber)

        # Search
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    SerialNumber.serial_no.ilike(search_term),
                    SerialNumber.item_code.ilike(search_term),
                    SerialNumber.item_name.ilike(search_term),
                )
            )

        # Filters
        if filters.item_code:
            query = query.filter(SerialNumber.item_code == filters.item_code)
        if filters.warehouse:
            query = query.filter(SerialNumber.warehouse == filters.warehouse)
        if filters.status:
            try:
                status_enum = SerialStatus(filters.status.lower())
                query = query.filter(SerialNumber.status == status_enum)
            except ValueError:
                pass  # Invalid status, ignore filter

        # Count total
        total = query.count()

        # Sorting
        sort_column = getattr(SerialNumber, filters.sort_by, SerialNumber.serial_no)
        if filters.sort_dir == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Pagination
        query = query.offset(pagination.offset).limit(pagination.limit)

        return PaginatedResult(
            items=query.all(),
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get_serial(self, serial_id: int) -> SerialNumber:
        """Get a serial number by ID.

        Args:
            serial_id: The serial number record ID.

        Returns:
            The SerialNumber object.

        Raises:
            NotFoundError: If serial number not found.
        """
        serial = self.db.query(SerialNumber).filter(SerialNumber.id == serial_id).first()
        if not serial:
            raise NotFoundError(f"Serial number {serial_id} not found")
        return serial

    def get_serial_by_no(self, serial_no: str) -> Optional[SerialNumber]:
        """Get a serial number by its serial number code.

        Args:
            serial_no: The serial number code.

        Returns:
            The SerialNumber object if found, None otherwise.
        """
        return self.db.query(SerialNumber).filter(SerialNumber.serial_no == serial_no).first()

    def get_serials_for_item(
        self,
        item_code: str,
        warehouse: Optional[str] = None,
        status: Optional[SerialStatus] = None,
    ) -> List[SerialNumber]:
        """Get all serial numbers for an item.

        Args:
            item_code: The item code.
            warehouse: Optional warehouse to filter by.
            status: Optional status to filter by.

        Returns:
            List of serial numbers for the item.
        """
        query = self.db.query(SerialNumber).filter(SerialNumber.item_code == item_code)

        if warehouse:
            query = query.filter(SerialNumber.warehouse == warehouse)
        if status:
            query = query.filter(SerialNumber.status == status)

        return query.order_by(SerialNumber.serial_no).all()

    def get_available_serials(
        self,
        item_code: str,
        warehouse: Optional[str] = None,
    ) -> List[SerialNumber]:
        """Get available (active) serial numbers for an item.

        Args:
            item_code: The item code.
            warehouse: Optional warehouse to filter by.

        Returns:
            List of available serial numbers.
        """
        return self.get_serials_for_item(
            item_code=item_code,
            warehouse=warehouse,
            status=SerialStatus.ACTIVE,
        )

    def get_serials_by_customer(self, customer: str) -> List[SerialNumber]:
        """Get all serial numbers assigned to a customer.

        Args:
            customer: The customer identifier.

        Returns:
            List of serial numbers for the customer.
        """
        return (
            self.db.query(SerialNumber)
            .filter(SerialNumber.customer == customer)
            .order_by(SerialNumber.delivery_date.desc())
            .all()
        )

    def get_serials_with_expiring_warranty(self, days_ahead: int = 30) -> List[SerialNumber]:
        """Get serial numbers with warranty expiring within the specified days.

        Args:
            days_ahead: Number of days to look ahead.

        Returns:
            List of serial numbers with expiring warranty.
        """
        from datetime import timedelta

        today = date.today()
        cutoff = today + timedelta(days=days_ahead)

        return (
            self.db.query(SerialNumber)
            .filter(
                SerialNumber.warranty_expiry_date.isnot(None),
                SerialNumber.warranty_expiry_date >= today,
                SerialNumber.warranty_expiry_date <= cutoff,
            )
            .order_by(SerialNumber.warranty_expiry_date.asc())
            .all()
        )

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create_serial(self, data: SerialCreateData) -> SerialNumber:
        """Create a new serial number.

        Args:
            data: Serial number creation data.

        Returns:
            The newly created SerialNumber.

        Raises:
            ConflictError: If serial number already exists.
        """
        # Check for duplicate serial number
        existing = self.get_serial_by_no(data.serial_no)
        if existing:
            raise ConflictError(f"Serial number '{data.serial_no}' already exists")

        # Parse status
        try:
            status = SerialStatus(data.status.lower())
        except ValueError:
            status = SerialStatus.ACTIVE

        serial = SerialNumber(
            serial_no=data.serial_no,
            item_code=data.item_code,
            warehouse=data.warehouse,
            batch_no=data.batch_no,
            status=status,
            purchase_document_type=data.purchase_document_type,
            purchase_document_no=data.purchase_document_no,
        )

        if self.principal:
            serial.created_by_id = self.principal.user_id

        self.db.add(serial)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(serial)
        return serial

    def create_serials_bulk(
        self,
        item_code: str,
        serial_nos: List[str],
        warehouse: Optional[str] = None,
        batch_no: Optional[str] = None,
    ) -> List[SerialNumber]:
        """Create multiple serial numbers at once.

        Args:
            item_code: The item code for all serials.
            serial_nos: List of serial number codes.
            warehouse: Optional warehouse for all serials.
            batch_no: Optional batch for all serials.

        Returns:
            List of created SerialNumber objects.

        Raises:
            ConflictError: If any serial number already exists.
        """
        # Check for existing serial numbers
        existing = (
            self.db.query(SerialNumber.serial_no)
            .filter(SerialNumber.serial_no.in_(serial_nos))
            .all()
        )
        if existing:
            existing_nos = [e[0] for e in existing]
            raise ConflictError(f"Serial numbers already exist: {', '.join(existing_nos)}")

        serials = []
        for serial_no in serial_nos:
            serial = SerialNumber(
                serial_no=serial_no,
                item_code=item_code,
                warehouse=warehouse,
                batch_no=batch_no,
                status=SerialStatus.ACTIVE,
            )
            if self.principal:
                serial.created_by_id = self.principal.user_id
            self.db.add(serial)
            serials.append(serial)

        self.db.flush()
        validator = SoftValidationService(self.db)
        for serial in serials:
            validator.validate_and_store(serial)
        return serials

    def update_serial(
        self,
        serial_id: int,
        warehouse: Optional[str] = None,
        batch_no: Optional[str] = None,
        description: Optional[str] = None,
        warranty_expiry_date: Optional[date] = None,
        amc_expiry_date: Optional[date] = None,
    ) -> SerialNumber:
        """Update a serial number.

        Args:
            serial_id: The serial number record ID.
            warehouse: New warehouse (if provided).
            batch_no: New batch (if provided).
            description: New description (if provided).
            warranty_expiry_date: New warranty expiry (if provided).
            amc_expiry_date: New AMC expiry (if provided).

        Returns:
            The updated SerialNumber.

        Raises:
            NotFoundError: If serial number not found.
        """
        serial = self.get_serial(serial_id)

        if warehouse is not None:
            serial.warehouse = warehouse
        if batch_no is not None:
            serial.batch_no = batch_no
        if description is not None:
            serial.description = description
        if warranty_expiry_date is not None:
            serial.warranty_expiry_date = warranty_expiry_date
        if amc_expiry_date is not None:
            serial.amc_expiry_date = amc_expiry_date

        serial.updated_at = datetime.utcnow()
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(serial)
        return serial

    def deliver_serial(
        self,
        serial_id: int,
        customer: str,
        delivery_document_type: str,
        delivery_document_no: str,
        delivery_date: Optional[date] = None,
    ) -> SerialNumber:
        """Mark a serial number as delivered to a customer.

        Args:
            serial_id: The serial number record ID.
            customer: The customer identifier.
            delivery_document_type: Type of delivery document.
            delivery_document_no: Delivery document number.
            delivery_date: Date of delivery (defaults to today).

        Returns:
            The updated SerialNumber.

        Raises:
            NotFoundError: If serial number not found.
            ValidationError: If serial is not in active status.
        """
        serial = self.get_serial(serial_id)

        if serial.status != SerialStatus.ACTIVE:
            raise ValidationError(
                f"Serial '{serial.serial_no}' is not active (status: {serial.status.value})"
            )

        serial.status = SerialStatus.DELIVERED
        serial.customer = customer
        serial.delivery_document_type = delivery_document_type
        serial.delivery_document_no = delivery_document_no
        serial.delivery_date = delivery_date or date.today()
        serial.warehouse = None  # Clear warehouse on delivery
        serial.updated_at = datetime.utcnow()

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(serial)
        return serial

    def return_serial(
        self,
        serial_id: int,
        warehouse: str,
    ) -> SerialNumber:
        """Mark a delivered serial number as returned.

        Args:
            serial_id: The serial number record ID.
            warehouse: The warehouse receiving the return.

        Returns:
            The updated SerialNumber.

        Raises:
            NotFoundError: If serial number not found.
            ValidationError: If serial is not in delivered status.
        """
        serial = self.get_serial(serial_id)

        if serial.status != SerialStatus.DELIVERED:
            raise ValidationError(
                f"Serial '{serial.serial_no}' is not delivered (status: {serial.status.value})"
            )

        serial.status = SerialStatus.RETURNED
        serial.warehouse = warehouse
        serial.updated_at = datetime.utcnow()

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(serial)
        return serial

    def reactivate_serial(self, serial_id: int) -> SerialNumber:
        """Reactivate a returned or inactive serial number.

        Args:
            serial_id: The serial number record ID.

        Returns:
            The updated SerialNumber.

        Raises:
            NotFoundError: If serial number not found.
            ValidationError: If serial cannot be reactivated.
        """
        serial = self.get_serial(serial_id)

        if serial.status not in (SerialStatus.RETURNED, SerialStatus.INACTIVE):
            raise ValidationError(
                f"Serial '{serial.serial_no}' cannot be reactivated from status: {serial.status.value}"
            )

        serial.status = SerialStatus.ACTIVE
        serial.updated_at = datetime.utcnow()

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(serial)
        return serial

    def deactivate_serial(self, serial_id: int) -> SerialNumber:
        """Deactivate a serial number.

        Args:
            serial_id: The serial number record ID.

        Returns:
            The updated SerialNumber.

        Raises:
            NotFoundError: If serial number not found.
        """
        serial = self.get_serial(serial_id)
        serial.status = SerialStatus.INACTIVE
        serial.updated_at = datetime.utcnow()
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(serial)
        return serial
