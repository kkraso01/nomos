from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..services.pipeline import run_pipeline, get_run
from ..services.ingestion import IngestionGateError

router = APIRouter(prefix="/pipeline", tags=["ingestion-pipeline"])


class RunIn(BaseModel):
    source_id: str
    ingest_key: str
    kind: str = "legislation"
    jurisdiction: str = "CY"
    raw_payload: str
    canonical_id: str
    title: str
    language: str = "en"
    effective_from: datetime | None = None
    court: str | None = None
    case_number: str | None = None


def _u(v):
    import uuid
    return uuid.UUID(v) if v else None


@router.post("/run", status_code=201)
def run_ingestion(payload: RunIn, ctx: dict = Depends(require_org),
                  db: Session = Depends(get_db)):
    metadata = {"court": payload.court, "case_number": payload.case_number}
    try:
        run = run_pipeline(db, source_id=_u(payload.source_id), ingest_key=payload.ingest_key,
                           kind=payload.kind, jurisdiction=payload.jurisdiction,
                           raw_payload=payload.raw_payload, canonical_id=payload.canonical_id,
                           title=payload.title, language=payload.language,
                           effective_from=payload.effective_from, metadata=metadata)
    except IngestionGateError as exc:
        raise HTTPException(403, str(exc))
    audit.record_audit(db, action="pipeline.run", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id,
                       detail={"kind": payload.kind, "canonical_id": payload.canonical_id,
                               "status": run.status})
    return {"run_id": str(run.id), "status": run.status, "stages": run.stages,
            "source_snapshot_id": str(run.source_snapshot_id) if run.source_snapshot_id else None,
            "document_id": str(run.document_id) if run.document_id else None}


@router.get("/{run_id}")
def run_status(run_id: str, ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    run = get_run(db, _u(run_id))
    if run is None:
        raise HTTPException(404, "Run not found")
    return {"run_id": str(run.id), "status": run.status, "stages": run.stages,
            "source_snapshot_id": str(run.source_snapshot_id) if run.source_snapshot_id else None,
            "error": run.error}