"""Citation graph: deterministic/evidenced edges between cases and provisions.

Edges must reference existing canonical nodes (validation on create) and carry
evidence + review status, especially for semantic treatment edges.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from . import Base


def _now():
    return datetime.now(timezone.utc)


class CitationEdge(Base):
    __tablename__ = "citation_edges"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=True)          # public corpus edges: null
    source_kind = Column(String(32), nullable=False)            # judgment_node | legislation_node
    source_ref = Column(String(512), nullable=False, index=True)
    target_kind = Column(String(32), nullable=False)
    target_ref = Column(String(512), nullable=False, index=True)
    # deterministic kinds: CITES / REFERENCES / REVERSE
    # semantic treatment kinds: FOLLOWS / DISTINGUISHES / APPROVES / CRITICISES / OVERRULES / REVERSED_BY
    treatment = Column(String(32), nullable=False, default="CITES")
    evidence = Column(JSON, nullable=True)                       # {quote, source_document_id, text_hash}
    review_status = Column(String(32), nullable=False, default="review_required")  # verified/review_required
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("ix_citation_source", "source_kind", "source_ref"),
        Index("ix_citation_target", "target_kind", "target_ref"),
    )

    SEMANTIC = {"FOLLOWS", "DISTINGUISHES", "APPROVES", "CRITICISES", "OVERRULES", "REVERSED_BY"}
    DETERMINISTIC = {"CITES", "REFERENCES", "REVERSED_BY"}