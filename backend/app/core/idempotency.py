"""Idempotency support for retry-sensitive writes."""
import uuid

from sqlalchemy import Column, String, Text, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from ..models import Base, utcnow


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(255), nullable=False, unique=True, index=True)
    response_json = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), default=utcnow)


def get_idempotent(db: Session, key: str):
    return db.query(IdempotencyRecord).filter_by(key=key).first()


def idempotent_execute(db: Session, key: str, fn) -> dict:
    """Execute a write fn exactly once for a given key.

    Returns a JSON-serializable dict. If a completed record already exists for
    the key, return the stored response without re-running the handler (safe
    for client retries).
    """
    import json

    rec = get_idempotent(db, key)
    if rec is not None and rec.status == "done" and rec.response_json:
        return json.loads(rec.response_json)
    result = fn()
    store_idempotent(db, key, json.dumps(result, default=str), status="done")
    return result


def store_idempotent(db: Session, key: str, response_json: str | None = None, status: str = "done"):
    rec = get_idempotent(db, key)
    if rec is None:
        rec = IdempotencyRecord(key=key, response_json=response_json, status=status)
        db.add(rec)
    else:
        rec.response_json = response_json
        rec.status = status
    db.commit()
    return rec