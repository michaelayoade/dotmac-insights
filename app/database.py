from __future__ import annotations

from datetime import datetime
from typing import Optional, Callable, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, create_engine, event, or_
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker, with_loader_criteria
from app.config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class SoftDeleteMixin:
    """Shared columns for soft-deletable models."""
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


def _soft_delete_criteria(cls: type[SoftDeleteMixin]) -> Any:
    return cls.is_deleted == False  # noqa: E712


def _company_criteria_factory(default_company: str) -> Callable[[type[Any]], Any]:
    def _criteria(cls: type[Any]) -> Any:
        return or_(
            cls.company == default_company,
            cls.company.is_(None),
        )

    return _criteria


@event.listens_for(Session, "do_orm_execute")
def _apply_soft_delete_filter(execute_state) -> None:
    """Exclude soft-deleted rows unless include_deleted is explicitly set."""
    if (
        execute_state.is_select
        and not execute_state.execution_options.get("include_deleted", False)
    ):
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                SoftDeleteMixin,
                _soft_delete_criteria,
                include_aliases=True,
            )
        )
    if (
        execute_state.is_select
        and settings.default_company
        and not execute_state.execution_options.get("include_all_companies", False)
    ):
        for mapper in Base.registry.mappers:
            cls = mapper.class_
            if hasattr(cls, "company"):
                execute_state.statement = execute_state.statement.options(
                    with_loader_criteria(
                        cls,
                        _company_criteria_factory(settings.default_company),
                        include_aliases=True,
                    )
                )


def get_db():
    """Dependency for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
