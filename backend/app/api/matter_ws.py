import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..core.tenancy import require_org
from ..core import audit
from ..storage.s3 import storage
from ..services import extract
from ..models.matter_ws import MatterDocument, MatterFact, MatterEvent, MatterIssue

router = APIRouter(prefix="/matters", tags=["matter-workspace"])


def _get_matter(db, org, mid):
    m = db.query(models.Matter).filter_by(id=mid, org_id=org).first()
    if m is None:
        raise HTTPException(404, "Matter not found")
    return m


def _require_doc(db, org, doc_id):
    d = db.query(MatterDocument).filter_by(id=doc_id, org_id=org).first()
    if d is None:
        raise HTTPException(404, "Document not found")
    return d


@router.post("/{matter_id}/documents", status_code=201)
def upload_matter_document(matter_id: uuid.UUID, file: UploadFile = File(...),
                           ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    data = file.file.read()
    text = ""
    if (file.content_type or "").startswith("text") or file.filename.endswith(".txt"):
        text = data.decode("utf-8", "replace")
    text_bytes = data
    key = f"{org}/matters/{matter_id}/{file.filename or 'doc.bin'}"
    storage.put_bytes(text_bytes, key, private=True,
                      content_type=file.content_type or "application/octet-stream")
    doc = MatterDocument(org_id=org, matter_id=matter_id, name=file.filename or "doc.bin",
                         storage_key=key, mime_type=file.content_type, extracted_text=text)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    audit.record_audit(db, action="matter.doc.upload", org_id=org, actor_user_id=ctx["user"].id,
                       resource_type="matter_document", resource_id=doc.id)
    return {"document_id": str(doc.id), "name": doc.name, "bytes": len(text_bytes),
            "extracted_text_chars": len(text)}


@router.post("/{matter_id}/documents/{doc_id}/extract")
def extract_document(matter_id: uuid.UUID, doc_id: uuid.UUID,
                     ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    doc = _require_doc(db, org, doc_id)
    text = doc.extracted_text or ""
    db.query(MatterFact).filter_by(document_id=doc_id, status="proposed").delete()
    db.query(MatterEvent).filter_by(document_id=doc_id, status="proposed").delete()

    for f in extract.extract_facts(text):
        db.add(MatterFact(org_id=org, matter_id=matter_id, document_id=doc_id, text=f["text"],
                          kind=f["kind"], char_start=f["char_start"], char_end=f["char_end"],
                          confidence=f["confidence"]))
    for ev in extract.extract_events(text):
        if not ev["event_date"]:
            continue  # chronology needs a definite date; undated events are dropped
        from datetime import datetime
        event_date = datetime.fromisoformat(ev["event_date"])
        db.add(MatterEvent(org_id=org, matter_id=matter_id, document_id=doc_id,
                           event_date=event_date, description=ev["description"],
                           char_start=ev["char_start"], char_end=ev["char_end"]))
    db.commit()
    facts = db.query(MatterFact).filter_by(document_id=doc_id).count()
    events = db.query(MatterEvent).filter_by(document_id=doc_id).count()
    audit.record_audit(db, action="matter.doc.extract", org_id=org, actor_user_id=ctx["user"].id,
                       resource_type="matter_document", resource_id=doc_id,
                       detail={"facts": facts, "events": events})
    return {"extracted_text_chars": len(text), "proposed_facts": facts, "proposed_events": events}


class FactDecision(BaseModel):
    status: str  # accepted / rejected


@router.post("/{matter_id}/facts/{fact_id}/decision")
def decide_fact(matter_id: uuid.UUID, fact_id: uuid.UUID, payload: FactDecision,
                ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    f = db.query(MatterFact).filter_by(id=fact_id, org_id=org, matter_id=matter_id).first()
    if f is None:
        raise HTTPException(404, "Fact not found")
    if payload.status not in ("accepted", "rejected"):
        raise HTTPException(400, "status must be accepted or rejected")
    f.status = payload.status
    db.commit()
    audit.record_audit(db, action="matter.fact.decide", org_id=org, actor_user_id=ctx["user"].id,
                       resource_type="matter_fact", resource_id=fact_id, detail={"status": payload.status})
    return {"fact_id": str(f.id), "status": f.status}


@router.get("/{matter_id}/facts")
def list_facts(matter_id: uuid.UUID, ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    rows = db.query(MatterFact).filter_by(matter_id=matter_id, org_id=org).all()
    return {"facts": [{"id": str(r.id), "kind": r.kind, "text": r.text, "status": r.status,
                       "char_start": r.char_start, "char_end": r.char_end, "confidence": r.confidence}
                      for r in rows]}


@router.get("/{matter_id}/chronology")
def chronology(matter_id: uuid.UUID, ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    rows = db.query(MatterEvent).filter_by(matter_id=matter_id, org_id=org)\
        .order_by(MatterEvent.event_date).all()
    return {"events": [{"id": str(r.id), "event_date": r.event_date and r.event_date.isoformat(),
                        "description": r.description, "status": r.status} for r in rows]}


@router.post("/{matter_id}/issues", status_code=201)
def create_issue(matter_id: uuid.UUID, text: str = Form(...), source_fact_id: str = Form(""),
                 ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    org = ctx["org_id"]
    _get_matter(db, org, matter_id)
    issue = MatterIssue(org_id=org, matter_id=matter_id, text=text,
                        source_fact_id=uuid.UUID(source_fact_id) if source_fact_id else None)
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return {"issue_id": str(issue.id), "text": issue.text, "status": issue.status}