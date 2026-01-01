"""Transaction helpers for service-level operations."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session


@contextmanager
def transactional_session(db: Session) -> Iterator[None]:
    """Provide an explicit transaction boundary with savepoint support."""
    with db.begin_nested():
        yield
