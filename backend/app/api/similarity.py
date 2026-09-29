from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..services.similarity import compare_cases

router = APIRouter(prefix="/similarity", tags=["similarity"])


class CompareIn(BaseModel):
    case_a: str
    case_b: str


@router.post("/compare")
def compare_cases_ep(payload: CompareIn, ctx: dict = Depends(require_org),
                     db: Session = Depends(get_db)):
    out = compare_cases(db, payload.case_a, payload.case_b)
    if not out["ok"]:
        raise HTTPException(404, f"Judgment(s) not found: {out['missing']}")
    audit.record_audit(db, action="similarity.cases", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="similarity",
                       detail={"a": payload.case_a, "b": payload.case_b})
    return out