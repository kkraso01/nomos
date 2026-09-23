from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..models.firm import create_precedent, search_internal

router = APIRouter(prefix="/firm", tags=["firm-knowledge"])


class PrecedentIn(BaseModel):
    title: str
    body: str
    kind: str = "precedent"


@router.post("/precedents", status_code=201)
def add_precedent(payload: PrecedentIn, ctx: dict = Depends(require_org),
                  db: Session = Depends(get_db)):
    p = create_precedent(db, org_id=ctx["org_id"], author_user_id=ctx["user"].id,
                         title=payload.title, body=payload.body, kind=payload.kind)
    audit.record_audit(db, action="firm.precedent.create", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="firm_precedent",
                       resource_id=p.id)
    return {"id": str(p.id), "title": p.title, "kind": p.kind}


@router.get("/search")
def internal_search(q: str = Query(...), limit: int = Query(10, le=50),
                    ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    rows = search_internal(db, org_id=ctx["org_id"], query=q, limit=limit)
    results = []
    for p, rank in rows:
        results.append({
            "id": str(p.id), "title": p.title, "kind": p.kind, "text": p.body,
            "internal": True, "primary_authority": False,  # never primary legal authority
            "score": round(float(rank or 0), 3),
        })
    return {"query": q, "count": len(results),
            "note": "Internal firm knowledge is permission-scoped and labelled internal (not primary legal authority).",
            "results": results}