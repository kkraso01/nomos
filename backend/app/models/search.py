import uuid
from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, String, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID

from . import Base


def _now():
    return datetime.now(timezone.utc)


class SearchEntry(Base):
    """Public search projection (PostgreSQL-backed lexical index by default).

    OpenSearch may substitute this via a SearchProvider; the model is opaque to
    the search API which only sees SearchResult objects.
    """
    __tablename__ = "search_entries"
    __table_args__ = (UniqueConstraint("kind", "canonical_ref", name="uq_search_kind_ref"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind = Column(String(32), nullable=False, index=True)  # legislation_node/judgment_node/source_document
    canonical_ref = Column(String(512), nullable=False)      # law-261-art-5 / ecli / case no
    canonical_id = Column(String(512), nullable=True, index=True)
    title = Column(String(1024), nullable=True)
    body = Column(Text, nullable=False)
    language = Column(String(16), nullable=True)
    ref_law = Column(String(64), nullable=True)
    ref_article = Column(String(64), nullable=True)
    ecli = Column(String(128), nullable=True)
    case_number = Column(String(128), nullable=True)
    court = Column(String(128), nullable=True)
    jurisdiction = Column(String(16), nullable=True)
    source_id = Column(UUID(as_uuid=True), nullable=True)
    external_url = Column(String(1024), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)