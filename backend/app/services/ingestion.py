import hashlib
import uuid
from typing import Any

from sqlalchemy import Column, DateTime, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from ..models import Base, utcnow
from ..config import settings


class LegalSource(Base):
    __tablename__ = "legal_sources"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registry_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(String(255), nullable=False)
    jurisdiction = Column(String(16), nullable=False)


class SourceSnapshot(Base):
    __tablename__ = "source_snapshots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    source_record_id = Column(String(255), nullable=False)
    source_url = Column(String(1024), nullable=True)
    observed_at = Column(DateTime(timezone=True), default=utcnow)
    published_at = Column(DateTime(timezone=True), nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    mime_type = Column(String(128), nullable=True)
    raw_payload = Column(Text, nullable=True)
    raw_object_storage_path = Column(String(1024), nullable=True)
    language = Column(String(16), nullable=True)
    adapter_version = Column(String(32), nullable=True)
    ingestion_run_id = Column(UUID(as_uuid=True), nullable=True)


class SourceDocument(Base):
    __tablename__ = "source_documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    canonical_key = Column(String(255), nullable=False, index=True)
    title = Column(String(1024), nullable=True)
    content_type = Column(String(128), nullable=True)
    language = Column(String(16), nullable=True)
    current_version_id = Column(UUID(as_uuid=True), nullable=True)
    raw_snapshot_id = Column(UUID(as_uuid=True), nullable=True)
    provenance = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


def content_hash(data: Any) -> str:
    return hashlib.sha256(str(data).encode("utf-8")).hexdigest()


class IngestionGateError(Exception):
    pass


class IngestionService:
    """Owns reuse gate, deduplication, raw persistence, canonical identity, versioning."""

    def __init__(self, db: Session, storage=None):
        self.db = db
        self.storage = storage

    def check_reuse_gate(self, registry) -> None:
        """Refuse bulk/systematic ingestion unless source is approved and enabled.

        In commercial-service mode, a source must ALSO be recorded as
        commercially reusable (commercial_reuse_allowed=True) before any bulk
        ingestion is permitted for resale. That flag is a human legal-clearance
        decision, not an assumption.
        """
        reasons = []
        if not getattr(registry, "bulk_ingestion_allowed", lambda: False)():
            reasons.append(f"reuse_status={registry.reuse_status}, adapter_enabled={registry.adapter_enabled}")
        if getattr(settings, "commercial_service_mode", False) and not registry.commercial_reuse_allowed:
            reasons.append("commercial_reuse_allowed=False (no recorded legal clearance for commercial resale)")
        if reasons:
            raise IngestionGateError(
                f"Bulk ingestion blocked for source {registry.name} ({'; '.join(reasons)})")

    def ingest_raw(self, registry, source_record_id: str, raw_payload: str, canonical_key: str,
                   title: str | None = None, language: str | None = None,
                   mime_type: str | None = None, published_at=None) -> SourceDocument:
        """Idempotent ingest: same source + content_hash -> no duplicate, return existing."""
        self.check_reuse_gate(registry)

        h = content_hash(raw_payload)
        existing_snapshot = self.db.query(SourceSnapshot).filter_by(
            source_id=registry.id, content_hash=h, source_record_id=source_record_id
        ).first()

        if existing_snapshot is None:
            snapshot = SourceSnapshot(
                source_id=registry.id,
                source_record_id=source_record_id,
                content_hash=h,
                raw_payload=raw_payload,
                mime_type=mime_type,
                language=language,
                published_at=published_at,
            )
            self.db.add(snapshot)
            self.db.flush()
        else:
            snapshot = existing_snapshot

        doc = self.db.query(SourceDocument).filter_by(
            source_id=registry.id, canonical_key=canonical_key
        ).first()
        if doc is None:
            doc = SourceDocument(
                source_id=registry.id,
                canonical_key=canonical_key,
                title=title,
                content_type=mime_type,
                language=language,
                raw_snapshot_id=snapshot.id,
                current_version_id=snapshot.id,
                provenance={"source_record_id": source_record_id, "content_hash": h},
            )
            self.db.add(doc)
        else:
            # Changed content creates a new version, not a destructive overwrite.
            if doc.current_version_id != snapshot.id:
                doc.current_version_id = snapshot.id
                doc.provenance = {"source_record_id": source_record_id, "content_hash": h}
        self.db.commit()
        return doc