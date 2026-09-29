from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..services.amendments import apply_amendment, amendments_between, diff_versions, AmendmentError

router = APIRouter(prefix="/amendments", tags=["temporal-legislation"])


class AmendmentIn(BaseModel):
    jurisdiction: str = "CY"
    affected_canonical_id: str
    operation: str
    effective_date: datetime
    publication_date: datetime | None = None
    node_type: str | None = None
    node_number: str | None = None
    new_text: str | None = None
    amending_canonical_id: str | None = None


@router.post("", status_code=201)
def record_amendment(payload: AmendmentIn, ctx: dict = Depends(require_org),
                     db: Session = Depends(get_db)):
    try:
        out = apply_amendment(
            db, jurisdiction=payload.jurisdiction, affected_canonical_id=payload.affected_canonical_id,
            operation=payload.operation, effective_date=payload.effective_date,
            publication_date=payload.publication_date, node_type=payload.node_type,
            node_number=payload.node_number, new_text=payload.new_text,
            amending_canonical_id=payload.amending_canonical_id)
    except AmendmentError as exc:
        raise HTTPException(400, str(exc))
    audit.record_audit(db, action="amendment.apply", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id,
                       detail={"law": payload.affected_canonical_id, "op": payload.operation,
                               "version": out["version_number"]})
    return out


@router.get("/{canonical_id}")
def list_amendments(canonical_id: str, ctx: dict = Depends(require_org),
                    db: Session = Depends(get_db)):
    return {"canonical_id": canonical_id, "amendments": amendments_between(db, canonical_id)}


@router.get("/{canonical_id}/diff/{from_version_id}/{to_version_id}")
def version_diff(canonical_id: str, from_version_id: str, to_version_id: str,
                 ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    import uuid
    return diff_versions(db, canonical_id, uuid.UUID(from_version_id), uuid.UUID(to_version_id))