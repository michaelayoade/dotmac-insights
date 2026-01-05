from __future__ import annotations

from datetime import datetime
from typing import Optional, Callable, Any, AsyncGenerator

from sqlalchemy import Boolean, DateTime, ForeignKey, create_engine, event, or_
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker, with_loader_criteria
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
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

    def soft_delete(self, deleted_by: Optional[int] = None) -> None:
        """Mark the record as soft-deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by_id = deleted_by


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
    db.rollback()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# =============================================================================
# ASYNC SESSION SUPPORT
# =============================================================================

def _make_async_url(url: str) -> str:
    """Convert sync database URL to async driver URL."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


async_engine = create_async_engine(
    _make_async_url(settings.database_url),
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async dependency for FastAPI routes requiring async database access."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Register soft validation after all models are available
def _register_soft_validation():
    """Deferred registration to avoid circular imports."""
    from app.validation.soft_validation import register_soft_validation
    register_soft_validation()


_register_soft_validation()
