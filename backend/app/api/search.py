from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..services.search import search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def do_search(q: str = Query(...), mode: str = Query("hybrid"), limit: int = Query(20, le=50),
              rerank: bool = Query(False),
              ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    results = search(db, q, mode=mode, limit=limit)
    payload = [
        {"kind": r.kind, "canonical_ref": r.canonical_ref, "title": r.title,
         "text": r.body, "language": r.language, "score": round(r.score, 3),
         "reason_for_match": r.reason, "metadata": r.metadata}
        for r in results
    ]
    reranked = False
    if rerank and payload:
        try:
            texts = [p["text"] or p["title"] or "" for p in payload]
            from ..services.rerank import RERANK_router
            ranked = RERANK_router(q, texts)
            score_of = {r["doc"]: round(r["score"], 3) for r in ranked}
            for p in payload:
                p["rerank_score"] = score_of.get(p["text"] or p["title"] or "", None)
            payload.sort(key=lambda p: (p["rerank_score"] is not None, p.get("rerank_score", -1e9)),
                         reverse=True)
            reranked = True
        except Exception:  # noqa: BLE001
            reranked = False  # graceful fallback to lexical order
    return {
        "query": q,
        "mode": mode,
        "reranked": reranked,
        "count": len(payload),
        "results": payload,
    }