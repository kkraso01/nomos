from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..services.search import search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def do_search(q: str = Query(...), mode: str = Query("hybrid"), limit: int = Query(20, le=50),
              ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    results = search(db, q, mode=mode, limit=limit)
    return {
        "query": q,
        "mode": mode,
        "count": len(results),
        "results": [
            {"kind": r.kind, "canonical_ref": r.canonical_ref, "title": r.title,
             "text": r.body, "language": r.language, "score": round(r.score, 3),
             "reason_for_match": r.reason, "metadata": r.metadata}
            for r in results
        ],
    }