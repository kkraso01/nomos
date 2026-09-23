"""Versioned procedural rules for deadline calculation."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID

from . import Base


def _now():
    return datetime.now(timezone.utc)


class ProceduralRule(Base):
    __tablename__ = "procedural_rules"
    __table_args__ = (UniqueConstraint("rule_key", "version_number", name="uq_rule_version"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_key = Column(String(128), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    jurisdiction = Column(String(16), nullable=False, default="CY")
    calculate_mode = Column(String(32), nullable=False)  # calendar_days | business_days | day_of_month | last_day_month
    base_days = Column(Integer, nullable=False, default=0)   # calendar/business days offset
    day_of_month = Column(Integer, nullable=True)            # for day_of_month mode
    direction = Column(String(16), nullable=False, default="after")  # after | before
    limit_type = Column(String(16), nullable=False, default="maximum")  # minimum | maximum
    ambiguous = Column(Boolean, nullable=False, default=False)   # triggers REVIEW_REQUIRED
    source_note = Column(Text, nullable=True)
    law_ref = Column(String(255), nullable=True)                 # e.g. Article 10 Law 261 of 2004
    version_number = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)