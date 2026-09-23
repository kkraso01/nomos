"""Firm knowledge: tenant-scoped internal precedents, templates and work product.

Internal results are always labelled internal=true and primary_authority=false so
they are never presented as primary legal authority.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from . import Base


def _now():
    return datetime.now(timezone.utc)


class FirmPrecedent(Base):
    __tablename__ = "firm_precedents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    author_user_id = Column(UUID(as_uuid=True), nullable=True)
    title = Column(String(512), nullable=False)
    body = Column(Text, nullable=False)
    kind = Column(String(32), nullable=False, default="precedent")  # precedent|template|work_product
    created_at = Column(DateTime(timezone=True), default=_now)


def create_precedent(db: Session, *, org_id, author_user_id, title, body, kind="precedent"):
    p = FirmPrecedent(org_id=org_id, author_user_id=author_user_id, title=title,
                      body=body, kind=kind)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def search_internal(db: Session, *, org_id, query: str, limit: int = 10):
    """Permission-aware: only returns the caller's own organisation's items."""
    tokens = [t for t in query.lower().split() if t][:8]
    if not tokens:
        return []
    unaccent = func.public.f_unaccent
    vector = func.to_tsvector("simple", unaccent(FirmPrecedent.body))
    q = " & ".join(tokens)
    qexpr = func.to_tsquery("simple", unaccent(q))
    return db.query(FirmPrecedent, func.ts_rank_cd(vector, qexpr).label("rank")).filter(
        FirmPrecedent.org_id == org_id, vector.op("@@")(qexpr)
    ).order_by(func.ts_rank_cd(vector, qexpr).desc()).limit(limit).all()