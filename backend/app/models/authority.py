"""Matter authority workspace + followed-item notifications."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, String, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from . import Base


def _now():
    return datetime.now(timezone.utc)


class MatterAuthority(Base):
    __tablename__ = "matter_authorities"
    __table_args__ = (UniqueConstraint("org_id", "matter_id", "canonical_ref", name="uq_authority"),
                      )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    matter_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    canonical_ref = Column(String(512), nullable=False)
    state = Column(String(32), nullable=False, default="relied_on")  # relied_on/adverse/distinguishable/rejected
    note = Column(Text, nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class FollowedItem(Base):
    __tablename__ = "followed_items"
    __table_args__ = (UniqueConstraint("org_id", "follow_key", name="uq_followed"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    follow_key = Column(String(512), nullable=False)   # canonical ref / topic
    follow_type = Column(String(32), nullable=False, default="ref")  # ref | topic
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


def set_authority(db: Session, *, org_id, matter_id, canonical_ref, state,
                  note=None, updated_by=None) -> MatterAuthority:
    row = db.query(MatterAuthority).filter_by(org_id=org_id, matter_id=matter_id,
                                              canonical_ref=canonical_ref).first()
    if row is None:
        row = MatterAuthority(org_id=org_id, matter_id=matter_id, canonical_ref=canonical_ref,
                              state=state, note=note, updated_by=updated_by)
        db.add(row)
    else:
        row.state = state
        row.note = note
        row.updated_by = updated_by
    db.commit()
    db.refresh(row)
    return row


def notify_followed(db: Session, org_id, followed_key, message) -> None:
    """Simple deterministic notification hook for newly ingested relevant data."""
    db.add(Notification(org_id=org_id, kind="followed_update",
                        reference=followed_key, message=message))
    db.commit()