from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..models.matter_ws import MatterFact
from ..services.research import grounded_research, validate_citation

router = APIRouter(prefix="/research", tags=["research"])


class ResearchIn(BaseModel):
    query: str
    matter_id: str | None = None
    limit: int = 10


class CitationCheckIn(BaseModel):
    text: str


@router.post("/query")
def research(payload: ResearchIn, ctx: dict = Depends(require_org),
             db: Session = Depends(get_db)):
    # Collect only ACCEPTED facts from the caller's own matter (tenant check).
    accepted = []
    if payload.matter_id:
        import uuid
        facts = db.query(MatterFact).filter_by(
            matter_id=uuid.UUID(payload.matter_id), org_id=ctx["org_id"],
            status="accepted").all()
        accepted = [f.text for f in facts]
    out = grounded_research(db, payload.query, limit=payload.limit, accepted_facts=accepted)
    audit.record_audit(db, action="research.query", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="research",
                       detail={"supported": out["supported"], "authorities": len(out["authorities"])})
    return out


@router.post("/validate-citation")
def check_citation(payload: CitationCheckIn, ctx: dict = Depends(require_org),
                   db: Session = Depends(get_db)):
    return validate_citation(db, payload.text)

@router.get("/vertical")
def research_vertical(q: str, matter_id: str | None = None,
                      as_of: datetime | None = None, limit: int = 20,
                      ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    from ..services.research_vertical import research as _research
    out = _research(db, q, as_of=as_of, limit=limit)
    audit.record_audit(db, action="research.vertical", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id,
                       detail={"q": q, "count": out["count"], "matter_id": matter_id})
    return out
