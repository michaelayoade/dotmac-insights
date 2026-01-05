from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.orm import Session, joinedload

from app.models.party import Party, PartyRole


def list_parties(
    db: Session,
    *,
    party_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    include_roles: bool = False,
) -> tuple[Sequence[Party], int]:
    query = db.query(Party)

    if include_roles:
        query = query.options(joinedload(Party.roles))

    if party_type:
        query = query.filter(Party.type == party_type)

    if status:
        query = query.filter(Party.status == status)

    if search:
        like = f"%{search}%"
        query = query.filter(
            Party.name.ilike(like)
            | Party.primary_email.ilike(like)
            | Party.primary_phone.ilike(like)
        )

    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    return rows, total


def get_party(
    db: Session,
    party_id: int,
    *,
    include_roles: bool = False,
) -> Optional[Party]:
    query = db.query(Party)
    if include_roles:
        query = query.options(joinedload(Party.roles))
    return query.filter(Party.id == party_id).first()


def create_party(db: Session, party: Party) -> Party:
    db.add(party)
    db.commit()
    db.refresh(party)
    return party


def update_party(db: Session, party: Party, updates: dict) -> Party:
    for key, value in updates.items():
        setattr(party, key, value)
    db.commit()
    db.refresh(party)
    return party


def add_role(db: Session, role: PartyRole) -> PartyRole:
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def list_roles(db: Session, party_id: int) -> Sequence[PartyRole]:
    return db.query(PartyRole).filter(PartyRole.party_id == party_id).all()


def count_parties(
    db: Session,
    *,
    party_type: Optional[str] = None,
    status: Optional[str] = None,
) -> int:
    """Count parties matching the given filters.

    Args:
        db: SQLAlchemy database session.
        party_type: Filter by type ('person' or 'organization').
        status: Filter by status ('active', 'inactive', 'blocked').

    Returns:
        Count of matching parties.
    """
    from sqlalchemy import func

    query = db.query(func.count(Party.id))

    if party_type:
        query = query.filter(Party.type == party_type)

    if status:
        query = query.filter(Party.status == status)

    return query.scalar() or 0
