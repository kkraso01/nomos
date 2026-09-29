from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..core.tenancy import require_org
from ..services.corpus import (ingest_legislation, ingest_judgment,
                               resolve_version_as_of, resolve_judgment_segments,
                               summarize_judgment, normalize_legislation_text)
from ..services.references import parse_reference
from ..models.corpus import LegislationNode, JudgmentNode

router = APIRouter(prefix="/corpus", tags=["corpus"])


class LegislationIngest(BaseModel):
    canonical_id: str
    title: str
    jurisdiction: str = "CY"
    language: str = "en"
    raw_text: str
    effective_from: datetime | None = None
    source_id: str | None = None


class JudgmentIngest(BaseModel):
    canonical_id: str
    title: str
    court: str | None = None
    case_number: str | None = None
    judgment_date: datetime | None = None
    raw_text: str
    source_id: str | None = None


class ParseOut(BaseModel):
    kind: str
    law: str | None
    article: str | None
    article_number: str | None
    case_number: str | None
    ecli: str | None
    confidence: float


@router.post("/legislation", status_code=201)
def create_legislation(payload: LegislationIngest, ctx: dict = Depends(require_org),
                       db: Session = Depends(get_db)):
    law, version, is_new = ingest_legislation(
        db, canonical_id=payload.canonical_id, title=payload.title,
        jurisdiction=payload.jurisdiction, raw_text=payload.raw_text,
        language=payload.language, effective_from=payload.effective_from,
        source_id=uuid_or_none(payload.source_id))
    return {"legislation_id": str(law.id), "version_id": str(version.id),
            "version_number": version.version_number, "is_new_version": is_new}


@router.get("/legislation/{canonical_id}/as-of")
def get_legislation_asof(canonical_id: str, as_of: datetime | None = None,
                         ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    version = resolve_version_as_of(db, canonical_id, as_of)
    if version is None:
        raise HTTPException(404, "Legislation not found")
    nodes = (db.query(LegislationNode).filter_by(version_id=version.id)
             .order_by(LegislationNode.sort_order).all())
    return {"version_id": str(version.id), "version_number": version.version_number,
            "effective_from": version.effective_from and version.effective_from.isoformat(),
            "effective_to": version.effective_to and version.effective_to.isoformat(),
            "status": version.status,
            "nodes": [{"node_type": n.node_type, "number": n.number,
                       "text": n.source_text or n.normalized_text,
                       "parent_id": str(n.parent_id) if n.parent_id else None}
                      for n in nodes]}


@router.post("/judgment", status_code=201)
def create_judgment(payload: JudgmentIngest, ctx: dict = Depends(require_org),
                    db: Session = Depends(get_db)):
    j, version, is_new = ingest_judgment(
        db, canonical_id=payload.canonical_id, title=payload.title, court=payload.court,
        case_number=payload.case_number, judgment_date=payload.judgment_date,
        raw_text=payload.raw_text, source_id=uuid_or_none(payload.source_id))
    return {"judgment_id": str(j.id), "version_id": str(version.id),
            "version_number": version.version_number, "is_new_version": is_new}


@router.get("/judgment/{canonical_id}/segments")
def judgment_segments(canonical_id: str, ctx: dict = Depends(require_org),
                      db: Session = Depends(get_db)):
    segs = resolve_judgment_segments(db, canonical_id)
    if segs is None:
        raise HTTPException(404, "Judgment not found")
    return {"canonical_id": canonical_id, "segments": segs}


@router.get("/judgment/{canonical_id}/summary")
def judgment_summary(canonical_id: str, ctx: dict = Depends(require_org),
                     db: Session = Depends(get_db)):
    out = summarize_judgment(db, canonical_id)
    if not out["ok"]:
        raise HTTPException(404, "Judgment not found")
    return out


@router.post("/parse-reference", response_model=ParseOut)
def parse_reference_ep(text: str = Body(..., embed=True),
                       ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    p = parse_reference(text)
    return ParseOut(kind=p.kind, law=p.law, article=p.article, article_number=p.article_number,
                    case_number=p.case_number, ecli=p.ecli, confidence=p.confidence)


def uuid_or_none(v):
    import uuid as _uuid
    return _uuid.UUID(v) if v else None