from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..services.corpus import (ingest_legislation, ingest_judgment,
                               resolve_version_as_of, resolve_judgment_segments,
                               summarize_judgment, node_contents_for_version)
from ..services.references import parse_reference

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
    jurisdiction: str = "CY"
    court: str | None = None
    court_id: str | None = None
    case_number: str | None = None
    ecli: str | None = None
    judgment_date: datetime | None = None
    judges: list[str] | None = None
    language: str | None = None
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


def _uuid(v):
    import uuid
    return uuid.UUID(v) if v else None


@router.post("/legislation", status_code=201)
def create_legislation(payload: LegislationIngest, ctx: dict = Depends(require_org),
                       db: Session = Depends(get_db)):
    law, version, is_new = ingest_legislation(
        db, canonical_id=payload.canonical_id, title=payload.title,
        jurisdiction=payload.jurisdiction, raw_text=payload.raw_text,
        language=payload.language, effective_from=payload.effective_from,
        source_id=_uuid(payload.source_id))
    return {"legislation_id": str(law.id), "version_id": str(version.id),
            "version_number": version.version_number, "is_new_version": is_new}


@router.get("/legislation/{canonical_id}/as-of")
def get_legislation_asof(canonical_id: str, as_of: datetime | None = None,
                         ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    version = resolve_version_as_of(db, canonical_id, as_of)
    if version is None:
        raise HTTPException(404, "Legislation not found")
    nodes = node_contents_for_version(db, version.id)
    return {"version_id": str(version.id), "version_number": version.version_number,
            "effective_from": version.effective_from and version.effective_from.isoformat(),
            "effective_to": version.effective_to and version.effective_to.isoformat(),
            "status": version.status, "nodes": nodes}


@router.post("/judgment", status_code=201)
def create_judgment(payload: JudgmentIngest, ctx: dict = Depends(require_org),
                    db: Session = Depends(get_db)):
    j, version, is_new = ingest_judgment(
        db, canonical_id=payload.canonical_id, title=payload.title,
        jurisdiction=payload.jurisdiction, court=payload.court, court_id=_uuid(payload.court_id),
        case_number=payload.case_number, ecli=payload.ecli, judgment_date=payload.judgment_date,
        judges=payload.judges, language=payload.language, raw_text=payload.raw_text,
        source_id=_uuid(payload.source_id))
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