from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..services.drafting import draft_memo

router = APIRouter(prefix="/draft", tags=["drafting"])


class MemoIn(BaseModel):
    facts: list[str] = []
    issues: list[str] = []
    citations: list[str] = []
    template: str | None = None


@router.post("/memo")
def memo(payload: MemoIn, ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    out = draft_memo(db, facts=payload.facts, issues=payload.issues,
                     citations=payload.citations, template=payload.template)
    audit.record_audit(db, action="draft.memo", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="draft",
                       detail={"verified": len(out["verified_citations"]),
                               "rejected": len(out["nonexistent_citations_rejected"])})
    return out