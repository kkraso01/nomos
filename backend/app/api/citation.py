from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..services import citation as svc

router = APIRouter(prefix="/citation", tags=["legal-graph"])


class CitationIn(BaseModel):
    source_case_id: str | None = None
    source_case_key: str | None = None
    source_jurisdiction: str = "CY"
    target_case_id: str | None = None
    target_case_key: str | None = None
    target_jurisdiction: str | None = None
    kind: str = "CITES"
    evidence_paragraph_id: str | None = None


class TreatmentIn(BaseModel):
    source_case_id: str | None = None
    source_case_key: str | None = None
    source_jurisdiction: str = "CY"
    target_case_id: str | None = None
    target_case_key: str | None = None
    target_jurisdiction: str | None = None
    treatment: str
    evidence_paragraph_id: str | None = None
    confidence: str | None = None


class ProvRefIn(BaseModel):
    jurisdiction: str = "CY"
    source_node_id: str
    target_node_id: str | None = None
    target_jurisdiction: str | None = None
    target_external_key: str | None = None
    source_text: str | None = None
    source_span_start: int | None = None
    source_span_end: int | None = None
    confidence: str = "high"


def _u(v):
    import uuid
    if not v or str(v).lower() in ("", "null", "none"):
        return None
    try:
        return uuid.UUID(v)
    except (ValueError, AttributeError, TypeError):
        return None


@router.post("/case", status_code=201)
def add_case_citation(payload: CitationIn, ctx: dict = Depends(require_org),
                      db: Session = Depends(get_db)):
    c = svc.create_case_citation(db, source_case_id=_u(payload.source_case_id),
                                 source_case_key=payload.source_case_key,
                                 source_jurisdiction=payload.source_jurisdiction,
                                 target_case_id=_u(payload.target_case_id),
                                 target_case_key=payload.target_case_key,
                                 target_jurisdiction=payload.target_jurisdiction,
                                 kind=payload.kind,
                                 evidence_paragraph_id=_u(payload.evidence_paragraph_id))
    audit.record_audit(db, action="graph.case_citation", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, detail={"kind": c.kind})
    return {"citation_id": str(c.id), "kind": c.kind, "review_status": c.review_status}


@router.post("/treatment", status_code=201)
def add_treatment(payload: TreatmentIn, ctx: dict = Depends(require_org),
                  db: Session = Depends(get_db)):
    t = svc.create_treatment(db, source_case_id=_u(payload.source_case_id),
                             source_case_key=payload.source_case_key,
                             source_jurisdiction=payload.source_jurisdiction,
                             target_case_id=_u(payload.target_case_id),
                             target_case_key=payload.target_case_key,
                             target_jurisdiction=payload.target_jurisdiction,
                             treatment=payload.treatment,
                             evidence_paragraph_id=_u(payload.evidence_paragraph_id),
                             confidence=payload.confidence)
    audit.record_audit(db, action="graph.treatment", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, detail={"treatment": t.treatment,
                                                             "review_status": t.review_status})
    return {"treatment_id": str(t.id), "treatment": t.treatment, "review_status": t.review_status}


@router.post("/provision-reference", status_code=201)
def add_provision_ref(payload: ProvRefIn, ctx: dict = Depends(require_org),
                      db: Session = Depends(get_db)):
    r = svc.create_provision_reference(db, source_node_id=_u(payload.source_node_id),
                                       target_node_id=_u(payload.target_node_id),
                                       source_jurisdiction=payload.jurisdiction,
                                       target_jurisdiction=payload.target_jurisdiction,
                                       target_external_key=payload.target_external_key,
                                       source_text=payload.source_text,
                                       source_span_start=payload.source_span_start,
                                       source_span_end=payload.source_span_end,
                                       confidence=payload.confidence)
    return {"reference_id": str(r.id), "confidence": r.confidence}


@router.post("/scan-provision-refs")
def scan_provision_refs(canonical_id: str, ctx: dict = Depends(require_org),
                        db: Session = Depends(get_db)):
    from ..services.provision_refs import scan_legislation
    out = scan_legislation(db, canonical_id)
    audit.record_audit(db, action="graph.scan_provision_refs", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id,
                       detail={"canonical_id": canonical_id, "created": out.get("created")})
    return out


@router.post("/enrich-judgment")
def enrich_judgment(canonical_id: str, applicable_law_canonical_id: str | None = None,
                    ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    from ..services.judgment_enrichment import enrich_judgment as _enrich
    out = _enrich(db, canonical_id, applicable_law_canonical_id)
    audit.record_audit(db, action="graph.enrich_judgment", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, detail={"canonical_id": canonical_id})
    return out


@router.get("/case/{ref}")
def expand_case(ref: str, ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    import uuid as _uuid
    try:
        case_id = _uuid.UUID(ref)
        return svc.expand_case(db, case_id=case_id)
    except (ValueError, AttributeError, TypeError):
        return svc.expand_case(db, case_key=ref)


@router.get("/provision/{node_id}")
def expand_provision(node_id: str, ctx: dict = Depends(require_org),
                     db: Session = Depends(get_db)):
    import uuid as _uuid
    try:
        return svc.expand_provision(db, node_id=_uuid.UUID(node_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(404, "provise node not found")