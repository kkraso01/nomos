"""Immutable, restartable, content-addressed ingestion pipeline.

Stages: DISCOVER->FETCH->RAW->PARSE->NORMALIZE->LINK->ENRICH->CHUNK->EMBED->INDEX
RAW snapshots are immutable and content-addressed (SHA256): same source+hash is a
no-op; changed hash is a new snapshot. Each stage is idempotent and recorded on the
IngestionRun; a failed later stage can be retried without reacquiring unchanged RAW
material. Every derived artifact records source_snapshot_id + parser/normalizer/
embedding versions + model_run_id.
"""
from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from ..models import SourceRegistry
from ..models.pipeline import IngestionRun, RunArtifact
from ..models.core import (Jurisdiction, LegalChunk, Legislation, Judgment)
from ..services.ingestion import (IngestionService, IngestionGateError,
                                  SourceSnapshot, content_hash)
from ..services import corpus as corpus_svc
from ..services import chunk as chunk_svc

STAGES = ["DISCOVER", "FETCH", "RAW", "PARSE", "NORMALIZE", "LINK", "ENRICH",
          "CHUNK", "EMBED", "INDEX"]

PARSER_VERSION = "l0-normalizer-1"
NORMALIZER_VERSION = "canonical-1"
_EMBED_PROVIDER = None  # set in task-7 (replaceable provider); None => skipped


def _rec(db, run, stage, atype, aid=None, akey=None, detail=None):
    db.add(RunArtifact(run_id=run.id, stage=stage, artifact_type=atype, artifact_id=aid,
                       artifact_key=akey, source_snapshot_id=run.source_snapshot_id,
                       parser_version=run.parser_version or PARSER_VERSION,
                       normalizer_version=run.normalizer_version or NORMALIZER_VERSION,
                       embedding_version=_EMBED_PROVIDER, detail=detail))


def get_run(db: Session, run_id) -> IngestionRun | None:
    return db.get(IngestionRun, run_id)


def run_pipeline(db: Session, *, source_id, ingest_key, kind: str = "legislation",
                 jurisdiction: str = "CY", raw_payload: str,
                 canonical_id: str, title: str, language: str = "en",
                 effective_from=None, metadata: dict | None = None,
                 fail_after: str | None = None) -> IngestionRun:
    h = content_hash(raw_payload)
    run = db.query(IngestionRun).filter_by(source_id=source_id, ingest_key=ingest_key,
                                           content_hash=h).first()
    if run is None:
        run = IngestionRun(source_id=source_id, ingest_key=ingest_key, content_hash=h,
                           kind=kind, jurisdiction=jurisdiction, parser_version=PARSER_VERSION,
                           normalizer_version=NORMALIZER_VERSION)
        db.add(run)
        db.flush()
    elif run.status == "done":
        return run  # fully completed & idempotent (same content hash -> no-op)

    run.status = "running"
    run.error = None
    db.commit()

    registry = db.get(SourceRegistry, source_id)
    if registry is None:
        raise IngestionGateError("Source not in registry")

    law = None
    version = None
    judgment = None
    jversion = None

    for stage in STAGES:
        if run.stages.get(stage) == "done":
            continue
        try:
            if stage == "DISCOVER":
                IngestionService(db).check_reuse_gate(registry)
                _ensure_jurisdiction(db, jurisdiction)
            elif stage == "FETCH":
                # fetch source document; for local/test ingestion the payload is supplied
                _rec(db, run, stage, "fetch", akey=canonical_id)
                db.flush()
            elif stage == "RAW":
                h = content_hash(raw_payload)
                snap = db.query(SourceSnapshot).filter_by(
                    source_id=registry.id, content_hash=h, source_record_id=ingest_key).first()
                if snap is None:
                    snap = SourceSnapshot(source_id=registry.id, source_record_id=ingest_key,
                                          content_hash=h, raw_payload=raw_payload,
                                          mime_type="text/plain", language=language)
                    db.add(snap)
                    db.flush()
                run.source_snapshot_id = snap.id  # reuse cached RAW on retry
                _rec(db, run, stage, "source_snapshot", aid=snap.id, detail={"content_hash": h})
            elif stage == "PARSE":
                corpus_svc.normalize_legislation_text(raw_payload)  # validates parse
                run.parser_version = PARSER_VERSION
            elif stage == "NORMALIZE":
                if kind == "legislation":
                    law, version, _ = corpus_svc.ingest_legislation(
                        db, canonical_id=canonical_id, title=title, jurisdiction=jurisdiction,
                        raw_text=raw_payload, language=language, source_id=registry.id,
                        effective_from=effective_from, source_snapshot_id=run.source_snapshot_id)
                    run.document_id = law.id
                    run.document_version_id = version.id
                else:
                    judgment, jversion, _ = corpus_svc.ingest_judgment(
                        db, canonical_id=canonical_id, title=title, jurisdiction=jurisdiction,
                        court=metadata and metadata.get("court"), case_number=metadata and metadata.get("case_number"),
                        raw_text=raw_payload, source_id=registry.id,
                        source_snapshot_id=run.source_snapshot_id)
                    run.document_id = judgment.id
                    run.document_version_id = jversion.id
                run.normalizer_version = NORMALIZER_VERSION
                _rec(db, run, stage, "canonical", aid=run.document_id,
                     akey=canonical_id, detail={"version": str(run.document_version_id)})
            elif stage == "LINK":
                db.flush()  # hook: cross-references/citations (task-5/6)
            elif stage == "ENRICH":
                db.flush()  # hook: extraction/enrichment (task-6)
            elif stage == "CHUNK":
                if kind == "legislation" and run.document_id:
                    law = db.get(Legislation, run.document_id)
                    chunk_svc.chunk_legislation(db, law, run.document_version_id, run.parser_version)
                elif kind != "legislation" and run.document_id:
                    judgment = db.get(Judgment, run.document_id)
                    chunk_svc.chunk_judgment(db, judgment, run.document_version_id, run.parser_version)
            elif stage == "EMBED":
                run.embedding_version = _embed_chunks(db, run)
            elif stage == "INDEX":
                db.flush()  # search projection already maintained by corpus ingest

            if fail_after == stage:
                raise RuntimeError(f"test failure after stage {stage}")
            run.stages[stage] = "done"
            db.commit()
        except Exception:  # noqa: BLE001
            run.status = "failed"
            run.error = f"{stage}: {__import__('traceback').format_exc()}"
            run.stages[stage] = "failed"
            db.commit()
            raise

    run.status = "done"
    db.commit()
    return run


def _ensure_jurisdiction(db: Session, code: str):
    if db.get(Jurisdiction, code) is None:
        db.add(Jurisdiction(code=code, name=code, node_terms={}, active=True))
        db.commit()

def _embed_chunks(db: Session, run) -> str | None:
    """Embed the run's chunks with the current embedding provider; persist vectors
    + provider metadata + model_run_id. Returns the embedding version or None."""
    from ..services.embedding import get_provider
    from ..models.core import LegalChunk
    prov = get_provider()
    if not prov.available() or run.document_version_id is None:
        return None
    chunks = db.query(LegalChunk).filter_by(version_id=run.document_version_id).all()
    if not chunks:
        return prov.meta()["version"]
    texts = [(c.hierarchy_context or c.text) for c in chunks]
    vecs = prov.embed(texts, is_query=False)
    model_run_id = uuid.uuid4()
    for c, v in zip(chunks, vecs):
        c.embedding = v
        c.embedding_provider = prov.meta()["provider"]
        c.embedding_model = prov.meta()["model"]
        c.embedding_version = prov.meta()["version"]
        c.embedding_dimensions = prov.meta()["dimensions"]
        c.embedding_created_at = datetime.now(timezone.utc)
        c.model_run_id = model_run_id
    db.flush()
    return prov.meta()["version"]
