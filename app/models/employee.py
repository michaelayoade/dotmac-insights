from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean, Text, Enum
from datetime import datetime
import enum
from app.database import Base


class EmploymentStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"
    ON_LEAVE = "on_leave"


class Employee(Base):
    """Employee records from ERPNext."""

    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)

    # External ID
    erpnext_id = Column(String(255), unique=True, index=True, nullable=True)
    chatwoot_agent_id = Column(Integer, index=True, nullable=True)

    # Basic info
    employee_number = Column(String(100), nullable=True, unique=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)

    # Position
    designation = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True, index=True)
    reports_to = Column(String(255), nullable=True)

    # Employment
    status = Column(Enum(EmploymentStatus), default=EmploymentStatus.ACTIVE, index=True)
    employment_type = Column(String(100), nullable=True)  # Full-time, Part-time, Contract
    date_of_joining = Column(DateTime, nullable=True)
    date_of_leaving = Column(DateTime, nullable=True)

    # Compensation (optional - may not sync this)
    salary = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(10), default="NGN")

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Employee {self.name} - {self.department}>"
