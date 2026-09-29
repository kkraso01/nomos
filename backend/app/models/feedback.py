import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, JSON, String
from sqlalchemy.dialects.postgresql import UUID

from . import Base


def _now():
    return datetime.now(timezone.utc)


class RelevanceFeedback(Base):
    """Lawyer relevance signal. Stored only (never used to fine-tune models)."""
    __tablename__ = "relevance_feedback"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    query = Column(String(512), nullable=False)
    canonical_ref = Column(String(512), nullable=False)
    judgement = Column(String(32), nullable=False)  # opened/saved_as_authority/rejected/irrelevant/adverse
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)