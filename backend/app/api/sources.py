import uuid

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..core.tenancy import require_org, get_current_user
from ..core import audit
from ..services.ingestion import IngestionService, IngestionGateError, content_hash
from ..services.ingestion import SourceDocument
from ..storage.s3 import storage
from ..schemas import SourceRegistryCreate, SourceRegistryOut, IngestRawRequest, IngestRawResponse

router = APIRouter(prefix="/sources", tags=["sources"])


# ---- Registry ----
@router.get("/registry", response_model=list[SourceRegistryOut])
def list_registry(db: Session = Depends(get_db)):
    return db.query(models.SourceRegistry).all()


@router.post("/registry", response_model=SourceRegistryOut, status_code=201)
def create_registry(payload: SourceRegistryCreate,
                    ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    existing = db.query(models.SourceRegistry).filter_by(name=payload.name).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Source already registered")
    row = models.SourceRegistry(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    audit.record_audit(db, action="source.registry.create", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="source", resource_id=row.id,
                       detail={"reuse_status": row.reuse_status})
    return row


@router.post("/registry/{source_id}/disable", response_model=SourceRegistryOut)
def disable_adapter(source_id: uuid.UUID, ctx: dict = Depends(require_org),
                    db: Session = Depends(get_db)):
    """Immediately disable an adapter. Actionable server-side emergency kill switch."""
    row = db.get(models.SourceRegistry, source_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    row.adapter_enabled = False
    db.commit()
    db.refresh(row)
    audit.record_audit(db, action="source.registry.disable", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="source", resource_id=row.id,
                       detail={"source": row.name})
    return row


class ClearanceIn(BaseModel):
    commercial_reuse_allowed: bool
    bulk_download_allowed: bool | None = None
    api_available: bool | None = None
    adapter_enabled: bool | None = None
    terms_checked_by: str | None = None
    terms_snapshot_hash: str | None = None
    licence: str | None = None
    licence_url: str | None = None
    reuse_status: str | None = None
    notes: str | None = None


@router.put("/registry/{source_id}/clearance", response_model=SourceRegistryOut)
def record_clearance(source_id: uuid.UUID, payload: ClearanceIn, ctx: dict = Depends(require_org),
                     db: Session = Depends(get_db)):
    """Record a human legal-clearance decision (incl. commercial reuse) for a source.

    This is an explicit, audited action — not an assumption. Until commercial
    reuse is recorded as allowed, bulk ingestion for the paid service is blocked.
    """
    from datetime import datetime, timezone
    row = db.get(models.SourceRegistry, source_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    row.terms_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    audit.record_audit(db, action="source.registry.clearance", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="source", resource_id=row.id,
                       detail={"source": row.name, "commercial_reuse_allowed": row.commercial_reuse_allowed})
    return row


# ---- Ingestion (reuse-gated) ----
@router.post("/{source_id}/ingest", response_model=IngestRawResponse, status_code=201)
def ingest_raw(source_id: uuid.UUID, payload: IngestRawRequest,
               ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    registry = db.get(models.SourceRegistry, source_id)
    if registry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not in registry")

    svc = IngestionService(db=db, storage=storage)
    try:
        before_hash = None
        existing_doc = db.query(SourceDocument).filter_by(
            source_id=registry.id, canonical_key=payload.canonical_key).first()
        if existing_doc:
            before_hash = existing_doc.current_version_id
        doc = svc.ingest_raw(
            registry=registry,
            source_record_id=payload.source_record_id or payload.canonical_key,
            raw_payload=payload.raw_payload,
            canonical_key=payload.canonical_key,
            title=payload.title, language=payload.language, mime_type=payload.mime_type,
        )
    except IngestionGateError as exc:
        audit.record_audit(db, action="source.ingest.blocked", org_id=ctx["org_id"],
                           actor_user_id=ctx["user"].id, resource_type="source",
                           resource_id=registry.id, detail={"reason": str(exc)})
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))

    created_new = existing_doc is None
    version_changed = (not created_new) and (before_hash != doc.current_version_id)
    deduplicated = (not created_new) and (not version_changed)

    audit.record_audit(db, action="source.ingest", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="source",
                       resource_id=registry.id,
                       detail={"canonical_key": payload.canonical_key, "hash": content_hash(payload.raw_payload)})
    return IngestRawResponse(
        document_id=doc.id, canonical_key=doc.canonical_key,
        content_hash=str(doc.current_version_id),
        created_new=created_new, version_changed=version_changed, deduplicated=deduplicated,
    )


# ---- Seed ----
@router.post("/seed", response_model=dict)
def seed_registry(ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    """Load engineering source seed (see SOURCE_REGISTRY_SEED.yaml). Idempotent by name."""
    from ..services.seed import seed_sources_from_yaml, seed_core
    path = __import__("app.config", fromlist=["settings"]).settings.root_dir
    counts = seed_core(db)
    counts.update(seed_sources_from_yaml(db))
    audit.record_audit(db, action="source.registry.seed", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="source")
    return counts