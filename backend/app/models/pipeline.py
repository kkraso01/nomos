import uuid
from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, JSON, String, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID

from . import Base


def _now():
    return datetime.now(timezone.utc)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (UniqueConstraint("source_id", "ingest_key", "content_hash", name="uq_run_source_key_hash"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    ingest_key = Column(String(255), nullable=False)
    content_hash = Column(String(64), nullable=False)
    kind = Column(String(32), nullable=False, default="legislation")  # legislation | judgment
    jurisdiction = Column(String(16), nullable=True)
    status = Column(String(16), nullable=False, default="running")   # running|done|failed
    stages = Column(JSON, nullable=False, default=dict)              # {STAGE: status}
    source_snapshot_id = Column(UUID(as_uuid=True), nullable=True)
    document_id = Column(UUID(as_uuid=True), nullable=True)   # canonical artifact (law/judgment id)
    document_version_id = Column(UUID(as_uuid=True), nullable=True)  # legislation/judgment version id
    parser_version = Column(String(64), nullable=True)
    normalizer_version = Column(String(64), nullable=True)
    embedding_version = Column(String(64), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class RunArtifact(Base):
    """Every derived artifact preserves its provenance back to the RAW snapshot."""
    __tablename__ = "run_artifacts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    stage = Column(String(32), nullable=False)
    artifact_type = Column(String(32), nullable=False)   # source_snapshot/legislation/node/chunk/...
    artifact_id = Column(UUID(as_uuid=True), nullable=True)
    artifact_key = Column(String(512), nullable=True)
    source_snapshot_id = Column(UUID(as_uuid=True), nullable=True)
    parser_version = Column(String(64), nullable=True)
    normalizer_version = Column(String(64), nullable=True)
    embedding_version = Column(String(64), nullable=True)
    model_run_id = Column(UUID(as_uuid=True), nullable=True)
    content_hash = Column(String(64), nullable=True)
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)