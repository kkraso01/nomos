"""Matter workspace models: private documents, facts, issues, chronology events.

All rows are org-scoped; every query MUST filter by org_id to preserve tenancy.
AI/extraction outputs link to evidence (source spans) rather than bare claims.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Column, ForeignKey, Integer, DateTime, String, Text)
from sqlalchemy.dialects.postgresql import UUID

from . import Base


def _now():
    return datetime.now(timezone.utc)


class MatterDocument(Base):
    __tablename__ = "matter_documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    matter_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(512), nullable=False)
    storage_key = Column(String(1024), nullable=True)
    mime_type = Column(String(128), nullable=True)
    extracted_text = Column(Text, nullable=True)
    parsed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class MatterFact(Base):
    __tablename__ = "matter_facts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    matter_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), nullable=True)
    text = Column(Text, nullable=False)
    kind = Column(String(32), nullable=True)      # party / date / amount / event
    status = Column(String(32), nullable=False, default="proposed")  # proposed/accepted/rejected
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)
    confidence = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class MatterEvent(Base):
    __tablename__ = "matter_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    matter_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), nullable=True)
    event_date = Column(DateTime(timezone=True), nullable=False)
    description = Column(Text, nullable=False)
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False, default="proposed")
    created_at = Column(DateTime(timezone=True), default=_now)


class MatterIssue(Base):
    __tablename__ = "matter_issues"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    matter_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    text = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="proposed")  # proposed/accepted/rejected
    source_fact_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)