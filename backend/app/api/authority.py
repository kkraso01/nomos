import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..models.authority import set_authority, MatterAuthority, FollowedItem, Notification, notify_followed
from ..models.search import SearchEntry

router = APIRouter(prefix="/matters", tags=["authority-workspace"])
follow_router = APIRouter(prefix="/follow", tags=["follow-notifications"])


def _get_matter(db, org, mid):
    from .. import models
    m = db.query(models.Matter).filter_by(id=mid, org_id=org).first()
    if m is None:
        raise HTTPException(404, "Matter not found")
    return m


class AuthorityIn(BaseModel):
    canonical_ref: str
    state: str
    note: str | None = None


@router.put("/{matter_id}/authorities/{canonical_ref}")
def upsert_authority(matter_id: uuid.UUID, canonical_ref: str, payload: AuthorityIn,
                     ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    if payload.state not in ("relied_on", "adverse", "distinguishable", "rejected"):
        raise HTTPException(400, "invalid state")
    # Authority must reference an existing corpus/provision node OR be a free internal reference.
    exists = db.query(SearchEntry).filter_by(canonical_ref=canonical_ref).first()
    if exists is None:
        raise HTTPException(400, "Authority not found in corpus")
    row = set_authority(db, org_id=org, matter_id=matter_id, canonical_ref=canonical_ref,
                        state=payload.state, note=payload.note, updated_by=ctx["user"].id)
    audit.record_audit(db, action="matter.authority.set", org_id=org, actor_user_id=ctx["user"].id,
                       resource_type="authority", detail={"state": payload.state})
    return {"authority_ref": canonical_ref, "state": row.state}


@router.get("/{matter_id}/authorities")
def list_authorities(matter_id: uuid.UUID, ctx: dict = Depends(require_org),
                     db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    rows = db.query(MatterAuthority).filter_by(matter_id=matter_id, org_id=org).all()
    return {"authorities": [{"canonical_ref": r.canonical_ref, "state": r.state,
                             "note": r.note,
                             "updated_at": r.updated_at.isoformat() if r.updated_at else None}
                            for r in rows]}


class FollowIn(BaseModel):
    follow_key: str
    label: str | None = None


@follow_router.post("", status_code=201)
def follow(ctx: dict = Depends(require_org), payload: FollowIn = None,
           db: Session = Depends(get_db)):
    org = ctx["org_id"]
    existing = db.query(FollowedItem).filter_by(org_id=org, follow_key=payload.follow_key).first()
    if existing is None:
        db.add(FollowedItem(org_id=org, follow_key=payload.follow_key, label=payload.label))
        db.commit()
    return {"follow_key": payload.follow_key}


@follow_router.post("/notify")
def manual_notify(follow_key: str = "topic:insolvency", ctx: dict = Depends(require_org),
                  db: Session = Depends(get_db)):
    """Deterministic hook: emit a source-backed update notification for a followed item."""
    notify_followed(db, ctx["org_id"], follow_key,
                    f"New relevant data became available for followed item '{follow_key}'.")
    return {"ok": True}


@follow_router.get("/notifications")
def list_notifications(ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    rows = db.query(Notification).filter_by(org_id=ctx["org_id"])\
        .order_by(Notification.created_at.desc()).limit(50).all()
    return {"notifications": [{"kind": n.kind, "reference": n.reference,
                               "message": n.message,
                               "created_at": n.created_at.isoformat() if n.created_at else None,
                               "read": n.read is not None} for n in rows]}