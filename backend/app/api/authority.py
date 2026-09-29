import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..core.tenancy import require_org
from ..core import audit
from ..models.authority import (set_authority, classify_authority, suggest_authority,
                                list_authorities, MatterAuthority, FollowedItem,
                                Notification)

router = APIRouter(prefix="/matters", tags=["authority-workspace"])
follow_router = APIRouter(prefix="/follow", tags=["follow-notifications"])


def _get_matter(db, org, mid):
    m = db.query(models.Matter).filter_by(id=mid, org_id=org).first()
    if m is None:
        raise HTTPException(404, "Matter not found")
    return m


def _out(a: MatterAuthority) -> dict:
    return {"id": str(a.id), "canonical_ref": a.canonical_ref, "jurisdiction": a.jurisdiction,
            "authority_type": a.authority_type, "source_scope": a.source_scope,
            "authority_name": a.authority_name, "classification": a.classification,
            "suggestion": a.suggestion, "suggestion_provenance": a.suggestion_provenance,
            "lawyer_note": a.lawyer_note, "matter_issue": a.matter_issue,
            "saved_by": str(a.saved_by) if a.saved_by else None,
            "saved_at": a.saved_at.isoformat() if a.saved_at else None,
            "evidence": _json(a.evidence),
            "temporal_applicability": _json(a.temporal_applicability)}


def _json(s):
    if not s:
        return None
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return s


class SaveIn(BaseModel):
    canonical_ref: str
    jurisdiction: str | None = None
    authority_type: str | None = None
    source_scope: str = "public"
    authority_name: str | None = None
    classification: str = "unclassified"
    lawyer_note: str | None = None
    matter_issue: str | None = None
    evidence: dict | None = None
    temporal_applicability: dict | None = None


class ClassifyIn(BaseModel):
    canonical_ref: str
    classification: str  # supporting|adverse|neutral|unclassified


class SuggestIn(BaseModel):
    canonical_ref: str
    suggestion: str  # supporting|adverse|neutral
    basis: str | None = "MODEL_INFERENCE"


@router.put("/{matter_id}/authorities", status_code=201)
def save_authority(matter_id: uuid.UUID, payload: SaveIn, ctx: dict = Depends(require_org),
                   db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    if payload.classification not in ("unclassified", "supporting", "adverse", "neutral"):
        raise HTTPException(400, "invalid classification")
    a = set_authority(db, org_id=org, matter_id=matter_id, canonical_ref=payload.canonical_ref,
                      jurisdiction=payload.jurisdiction, authority_type=payload.authority_type,
                      source_scope=payload.source_scope, authority_name=payload.authority_name,
                      classification=payload.classification, lawyer_note=payload.lawyer_note,
                      saved_by=ctx["user"].id, matter_issue=payload.matter_issue,
                      evidence=json.dumps(payload.evidence) if payload.evidence is not None else None,
                      temporal_applicability=json.dumps(payload.temporal_applicability)
                      if payload.temporal_applicability is not None else None)
    audit.record_audit(db, action="matter.authority.save", org_id=org, actor_user_id=ctx["user"].id,
                       resource_type="authority",
                       detail={"canonical_ref": payload.canonical_ref,
                               "classification": a.classification})
    return _out(a)


@router.post("/{matter_id}/authorities/classify", status_code=200)
def classify(matter_id: uuid.UUID, payload: ClassifyIn, ctx: dict = Depends(require_org),
             db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    if payload.classification not in ("supporting", "adverse", "neutral", "unclassified"):
        raise HTTPException(400, "invalid classification")
    row, is_new = classify_authority(db, org_id=org, matter_id=matter_id,
                                     canonical_ref=payload.canonical_ref,
                                     classification=payload.classification, saved_by=ctx["user"].id)
    audit.record_audit(db, action="matter.authority.classify", org_id=org,
                       actor_user_id=ctx["user"].id,
                       detail={"canonical_ref": payload.canonical_ref,
                               "classification": payload.classification})
    return _out(row)


@router.post("/{matter_id}/authorities/suggest", status_code=200)
def suggest(matter_id: uuid.UUID, payload: SuggestIn, ctx: dict = Depends(require_org),
            db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    if payload.suggestion not in ("supporting", "adverse", "neutral"):
        raise HTTPException(400, "suggestion must be supporting|adverse|neutral")
    row = suggest_authority(db, org_id=org, matter_id=matter_id, canonical_ref=payload.canonical_ref,
                            suggestion=payload.suggestion, basis=payload.basis)
    return _out(row)


@router.get("/{matter_id}/authorities")
def list_authorities_ep(matter_id: uuid.UUID, classification: str | None = None,
                        ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    rows = list_authorities(db, org_id=org, matter_id=matter_id)
    if classification:
        rows = [a for a in rows if a.classification == classification]
    return {"authorities": [_out(a) for a in rows],
            "count": len(rows)}


@router.get("/{matter_id}/authorities/folders")
def authority_folders(matter_id: uuid.UUID, ctx: dict = Depends(require_org),
                      db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    rows = list_authorities(db, org_id=org, matter_id=matter_id)
    folders = {}
    for a in rows:
        folders.setdefault(a.classification, []).append(_out(a))
    return {"folders": folders}


@follow_router.post("", status_code=201)
def follow(ctx: dict = Depends(require_org), payload: dict = None,
           db: Session = Depends(get_db)):
    from pydantic import BaseModel as _BM

    class _F(_BM):
        follow_key: str
        label: str | None = None

    p = _F(**payload or {})
    org = ctx["org_id"]
    existing = db.query(FollowedItem).filter_by(org_id=org, follow_key=p.follow_key).first()
    if existing is None:
        db.add(FollowedItem(org_id=org, follow_key=p.follow_key, label=p.label))
        db.commit()
    return {"follow_key": p.follow_key}


@follow_router.post("/notify")
def manual_notify(follow_key: str = "topic:insolvency", ctx: dict = Depends(require_org),
                  db: Session = Depends(get_db)):
    db.add(Notification(org_id=ctx["org_id"], kind="followed_update", reference=follow_key,
                        message=f"New relevant data became available for followed item '{follow_key}'."))
    db.commit()
    return {"ok": True}


@follow_router.get("/notifications")
def list_notifications(ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    rows = db.query(Notification).filter_by(org_id=ctx["org_id"])\
        .order_by(Notification.created_at.desc()).limit(50).all()
    return {"notifications": [{"kind": n.kind, "reference": n.reference, "message": n.message,
                               "created_at": n.created_at.isoformat() if n.created_at else None,
                               "read": n.read is not None} for n in rows]}