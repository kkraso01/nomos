"""Matter authority workspace + followed-item notifications.

An authority is a REFERENCE to a canonical source (no duplication of canonical
content into the matter). Classification is lawyer-controlled; the system may
store a SUGGESTION (provenance=MODEL_INFERENCE) that is never silently accepted.
Tenant isolation is deny-by-default (org_id + matter_id scope on every query).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, DateTime, String, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from . import Base


def _now():
    return datetime.now(timezone.utc)


class MatterAuthority(Base):
    __tablename__ = "matter_authorities"
    __table_args__ = (UniqueConstraint("org_id", "matter_id", "canonical_ref", name="uq_authority"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    matter_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    canonical_ref = Column(String(512), nullable=False)   # reference to canonical authority (no duplication)
    jurisdiction = Column(String(16), nullable=True)
    authority_type = Column(String(32), nullable=True)    # legislation | judgment | source_document | other
    source_scope = Column(String(16), nullable=False, default="public")  # public | private
    authority_name = Column(String(512), nullable=True)   # display title/name
    # Lawyer-controlled classification (the decision of record):
    classification = Column(String(32), nullable=False, default="unclassified")  # supporting|adverse|neutral|unclassified
    # System suggestion (never silently accepted):
    suggestion = Column(String(32), nullable=True)        # supporting|adverse|neutral
    suggestion_provenance = Column(String(32), nullable=True, default="MODEL_INFERENCE")
    lawyer_note = Column(Text, nullable=True)
    saved_by = Column(UUID(as_uuid=True), nullable=True)
    saved_at = Column(DateTime(timezone=True), default=_now)
    matter_issue = Column(String(512), nullable=True)     # relevant matter issue the authority supports/opposes
    evidence = Column(Text, nullable=True)                # JSON: evidence links (paragraph_id, spans, chunks)
    temporal_applicability = Column(Text, nullable=True)  # JSON: {version_number,effective_from,effective_to}
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class FollowedItem(Base):
    __tablename__ = "followed_items"
    __table_args__ = (UniqueConstraint("org_id", "follow_key", name="uq_followed"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    follow_key = Column(String(512), nullable=False)
    follow_type = Column(String(32), nullable=False, default="ref")
    label = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    kind = Column(String(32), nullable=False)  # followed_update / new_authority
    reference = Column(String(512), nullable=True)
    message = Column(Text, nullable=False)
    read = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


def set_authority(db: Session, *, org_id, matter_id, canonical_ref, jurisdiction=None,
                  authority_type=None, source_scope="public", authority_name=None,
                  classification="unclassified", lawyer_note=None, saved_by=None,
                  matter_issue=None, evidence=None, temporal_applicability=None) -> MatterAuthority:
    """Save (or update) an authority on a matter. References the canonical authority."""
    row = db.query(MatterAuthority).filter_by(org_id=org_id, matter_id=matter_id,
                                              canonical_ref=canonical_ref).first()
    if row is None:
        row = MatterAuthority(org_id=org_id, matter_id=matter_id, canonical_ref=canonical_ref,
                              jurisdiction=jurisdiction, authority_type=authority_type,
                              source_scope=source_scope, authority_name=authority_name,
                              classification=classification, lawyer_note=lawyer_note,
                              saved_by=saved_by, saved_at=_now(), matter_issue=matter_issue,
                              evidence=evidence, temporal_applicability=temporal_applicability)
        db.add(row)
    else:
        for attr, val in (("jurisdiction", jurisdiction), ("authority_type", authority_type),
                          ("source_scope", source_scope), ("authority_name", authority_name),
                          ("lawyer_note", lawyer_note), ("matter_issue", matter_issue),
                          ("evidence", evidence), ("temporal_applicability", temporal_applicability)):
            if val is not None:
                setattr(row, attr, val)
    db.commit()
    db.refresh(row)
    return row


def classify_authority(db: Session, *, org_id, matter_id, canonical_ref, classification,
                       saved_by=None) -> tuple[MatterAuthority, bool]:
    """Lawyer-controlled classification. Returns (row, is_new)."""
    row = db.query(MatterAuthority).filter_by(org_id=org_id, matter_id=matter_id,
                                              canonical_ref=canonical_ref).first()
    if row is None:
        row = set_authority(db, org_id=org_id, matter_id=matter_id, canonical_ref=canonical_ref,
                            classification="unclassified", saved_by=saved_by)
        is_new = True
    else:
        is_new = False
    row.classification = classification
    db.commit()
    db.refresh(row)
    return row, is_new


def suggest_authority(db: Session, *, org_id, matter_id, canonical_ref, suggestion,
                      basis=None) -> MatterAuthority:
    """Store a system suggestion (MODEL_INFERENCE); does NOT change the lawyer decision."""
    row = db.query(MatterAuthority).filter_by(org_id=org_id, matter_id=matter_id,
                                              canonical_ref=canonical_ref).first()
    if row is None:
        row = MatterAuthority(org_id=org_id, matter_id=matter_id, canonical_ref=canonical_ref,
                              classification="unclassified", source_scope="public")
        db.add(row)
        db.flush()
    row.suggestion = suggestion
    row.suggestion_provenance = basis or "MODEL_INFERENCE"
    db.commit()
    db.refresh(row)
    return row


def list_authorities(db: Session, *, org_id, matter_id) -> list[MatterAuthority]:
    return db.query(MatterAuthority).filter_by(org_id=org_id, matter_id=matter_id)\
        .order_by(MatterAuthority.saved_at).all()