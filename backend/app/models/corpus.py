"""Public legal corpus models: versioned legislation and judgments.

Never overwrite legislation text. Each content state is a version; nodes carry
their own effective intervals enabling temporal (as-of-date) resolution.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, JSON,
                        String, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base


def _now():
    return datetime.now(timezone.utc)


class Legislation(Base):
    __tablename__ = "legislation"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_id = Column(String(255), nullable=False, index=True)
    title = Column(String(1024), nullable=False)
    jurisdiction = Column(String(16), nullable=False)
    source_id = Column(UUID(as_uuid=True), nullable=True)
    language = Column(String(16), nullable=True)
    current_version_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class LegislationVersion(Base):
    __tablename__ = "legislation_versions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legislation_id = Column(UUID(as_uuid=True), ForeignKey("legislation.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(64), nullable=False)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="current")  # current/superseded/repealed
    supersedes_version_id = Column(UUID(as_uuid=True), nullable=True)
    source_snapshot_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    __table_args__ = (UniqueConstraint("legislation_id", "version_number", name="uq_leg_version"),)


class LegislationNode(Base):
    __tablename__ = "legislation_nodes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id = Column(UUID(as_uuid=True), ForeignKey("legislation_versions.id"), nullable=False, index=True)
    parent_id = Column(UUID(as_uuid=True), nullable=True)
    node_type = Column(String(32), nullable=False)  # LAW/PART/CHAPTER/ARTICLE/SUBARTICLE/PARAGRAPH
    number = Column(String(64), nullable=True)
    title = Column(String(512), nullable=True)
    source_text = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)
    language = Column(String(16), nullable=True)
    sort_order = Column(Integer, nullable=True, default=0)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    source_locator = Column(JSON, nullable=True)


class Judgment(Base):
    __tablename__ = "judgments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_id = Column(String(255), nullable=False, index=True)
    title = Column(String(1024), nullable=True)
    court = Column(String(128), nullable=True)
    case_number = Column(String(255), nullable=True)
    ecli = Column(String(128), nullable=True, index=True)
    judgment_date = Column(DateTime(timezone=True), nullable=True)
    source_id = Column(UUID(as_uuid=True), nullable=True)
    current_version_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class JudgmentVersion(Base):
    __tablename__ = "judgment_versions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    judgment_id = Column(UUID(as_uuid=True), ForeignKey("judgments.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(64), nullable=False)
    source_snapshot_id = Column(UUID(as_uuid=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    __table_args__ = (UniqueConstraint("judgment_id", "version_number", name="uq_judgment_version"),)


class JudgmentNode(Base):
    __tablename__ = "judgment_nodes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id = Column(UUID(as_uuid=True), ForeignKey("judgment_versions.id"), nullable=False, index=True)
    para_number = Column(String(64), nullable=True)
    text = Column(Text, nullable=False)
    segment_type = Column(String(32), nullable=True)  # facts/procedural_history/holding/legal_analysis/order
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)
    sort_order = Column(Integer, nullable=True, default=0)
    language = Column(String(16), nullable=True)