import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..services.citation import create_edge, cited_authorities, citing_authorities, CitationValidationError
from ..models.citation import CitationEdge

router = APIRouter(prefix="/citation", tags=["citation"])


class EdgeIn(BaseModel):
    source_kind: str
    source_ref: str
    target_kind: str
    target_ref: str
    treatment: str = "CITES"
    evidence: dict | None = None
    review_status: str | None = None
    note: str | None = None


def _edge_out(e: CitationEdge) -> dict:
    return {"id": str(e.id), "source_kind": e.source_kind, "source_ref": e.source_ref,
            "target_kind": e.target_kind, "target_ref": e.target_ref,
            "treatment": e.treatment, "review_status": e.review_status,
            "evidence": e.evidence}


@router.post("", status_code=201)
def add_edge(payload: EdgeIn, ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    try:
        edge = create_edge(db, source_kind=payload.source_kind, source_ref=payload.source_ref,
                           target_kind=payload.target_kind, target_ref=payload.target_ref,
                           treatment=payload.treatment, evidence=payload.evidence,
                           review_status=payload.review_status, org_id=ctx["org_id"], note=payload.note)
    except CitationValidationError as exc:
        raise HTTPException(400, str(exc))
    db.add(edge)
    db.commit()
    db.refresh(edge)
    audit.record_audit(db, action="citation.edge.create", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="citation_edge", resource_id=edge.id,
                       detail={"treatment": edge.treatment})
    return _edge_out(edge)


@router.get("/node/{kind}/{ref:path}")
def traverse(kind: str, ref: str, ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    cited = cited_authorities(db, kind, ref)
    citing = citing_authorities(db, kind, ref)
    return {
        "node": {"kind": kind, "ref": ref},
        "cited_authorities": [_edge_out(e) for e in cited],
        "citing_authorities": [_edge_out(e) for e in citing],
        "counts": {"cited": len(cited), "citing": len(citing)},
    }