from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..services.hybrid import hybrid_search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/hybrid")
def hybrid(q: str = Query(...), mode: str = Query("hybrid"), limit: int = Query(10, le=50),
           as_of: datetime | None = Query(None),
           ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    out = hybrid_search(db, q, as_of=as_of, limit=limit, mode=mode)
    audit.record_audit(db, action="search.hybrid", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, detail={"q": q, "mode": mode,
                                                             "count": out["count"]})
    return out