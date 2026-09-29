from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..services.assistant import grounded_answer

router = APIRouter(prefix="/assistant", tags=["research-assistant"])


class AskIn(BaseModel):
    query: str
    as_of: datetime | None = None
    matter_id: str | None = None
    limit: int = 6


@router.post("/ask")
def ask(payload: AskIn, ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    out = grounded_answer(db, query=payload.query, as_of=payload.as_of,
                          matter_id=payload.matter_id, org_id=ctx["org_id"],
                          limit=payload.limit)
    audit.record_audit(db, action="assistant.ask", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id,
                       detail={"supported": out["supported"],
                               "authorities": len(out["authorities"]),
                               "propositions": len(out["propositions"])})
    return out