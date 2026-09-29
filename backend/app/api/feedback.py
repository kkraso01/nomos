from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..models.feedback import RelevanceFeedback

router = APIRouter(prefix="/feedback", tags=["feedback"])

VALID = {"opened", "saved_as_authority", "rejected", "irrelevant", "adverse"}


class FeedbackIn(BaseModel):
    query: str
    canonical_ref: str
    judgement: str
    detail: dict | None = None


@router.post("", status_code=201)
def store_feedback(payload: FeedbackIn, ctx: dict = Depends(require_org),
                   db: Session = Depends(get_db)):
    if payload.judgement not in VALID:
        raise HTTPException(400, f"judgment must be one of {sorted(VALID)}")
    db.add(RelevanceFeedback(org_id=ctx["org_id"], query=payload.query,
                             canonical_ref=payload.canonical_ref,
                             judgement=payload.judgement, detail=payload.detail))
    db.commit()
    audit.record_audit(db, action="feedback.store", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id,
                       detail={"query": payload.query, "judgement": payload.judgement})
    # Stored for later curation only — never used to fine-tune models automatically.
    return {"stored": True, "note": "Signal stored for curation; no model training from clicks."}