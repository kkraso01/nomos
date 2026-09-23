import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from . import Base


class ModelRunLog(Base):
    __tablename__ = "model_run_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=True)
    capability = Column(String(64), nullable=False)
    provider = Column(String(128), nullable=True)
    model = Column(String(128), nullable=True)
    input_hash = Column(String(64), nullable=True)
    success = Column(Boolean, nullable=False)
    reason = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))