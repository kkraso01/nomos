"""Task-3 acceptance: immutable, content-addressed, restartable ingestion pipeline."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.models.core import LegalChunk
from app.services.pipeline import run_pipeline
from app.services.ingestion import IngestionGateError

client = TestClient(app)


def _setup():
    p = f"pip{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.post("/sources/seed", headers=h)
    reg = client.get("/sources/registry", headers=h).json()
    cy = next(s for s in reg if s["name"] == "Cyprus National Open Data Portal")
    assert cy["commercial_reuse_allowed"] is True
    return cy["id"]


PAYLOAD = "Article 1. Short title.\n(1) This Law may be cited as the Pipeline Law.\nArticle 5. Winding up.\n(1) A company may be wound up by the court in the event of insolvency."


def test_content_addressed_and_changed_snapshot():
    src = _setup()
    s = SessionLocal()
    key = f"pip-{uuid.uuid4().hex[:6]}"
    r1 = run_pipeline(s, source_id=uuid.UUID(src), ingest_key=key, raw_payload=PAYLOAD,
                      canonical_id="PL-1", title="Pipeline Law", jurisdiction="CY")
    assert r1.status == "done" and r1.source_snapshot_id
    snap1 = r1.source_snapshot_id

    # same source+hash -> idempotent no-op, same snapshot
    r1b = run_pipeline(s, source_id=uuid.UUID(src), ingest_key=key, raw_payload=PAYLOAD,
                       canonical_id="PL-1", title="Pipeline Law", jurisdiction="CY")
    assert r1b.status == "done" and r1b.source_snapshot_id == snap1

    # same key, CHANGED content -> new run + new snapshot (no destructive overwrite)
    r2 = run_pipeline(s, source_id=uuid.UUID(src), ingest_key=key,
                      raw_payload=PAYLOAD + "\nCHANGED content.",
                      canonical_id="PL-1", title="Pipeline Law", jurisdiction="CY")
    assert r2.source_snapshot_id != snap1
    s.close()


def test_restart_after_failure_reuses_cached_raw():
    src = _setup()
    s = SessionLocal()
    key = f"pipf-{uuid.uuid4().hex[:6]}"
    with pytest.raises(RuntimeError):
        run_pipeline(s, source_id=uuid.UUID(src), ingest_key=key, raw_payload=PAYLOAD,
                     canonical_id="PL-2", title="Pipeline Law", jurisdiction="CY", fail_after="PARSE")
    from app.models.pipeline import IngestionRun
    from app.services.pipeline import content_hash
    failed = s.query(IngestionRun).filter_by(source_id=uuid.UUID(src), ingest_key=key,
                                             content_hash=content_hash(PAYLOAD)).one()
    assert failed.status == "failed"
    snap_after_failure = failed.source_snapshot_id
    assert snap_after_failure is not None  # RAW was persisted before the PARSE failure

    # retry resumes from cached RAW: snapshot id unchanged (no refetch)
    done = run_pipeline(s, source_id=uuid.UUID(src), ingest_key=key, raw_payload=PAYLOAD,
                        canonical_id="PL-2", title="Pipeline Law", jurisdiction="CY")
    assert done.status == "done"
    assert done.source_snapshot_id == snap_after_failure
    s.close()


def test_pipeline_creates_legal_chunks():
    src = _setup()
    s = SessionLocal()
    cid = f"PL-{uuid.uuid4().hex[:6]}"
    run_pipeline(s, source_id=uuid.UUID(src), ingest_key=cid, raw_payload=PAYLOAD,
                 canonical_id=cid, title="Pipeline Law", jurisdiction="CY")
    chunks = s.query(LegalChunk).filter(LegalChunk.document_key == cid).count()
    assert chunks >= 2  # article/paragraph structural chunk units
    s.close()


def test_pipeline_api_endpoint():
    src = _setup()
    p = f"api{uuid.uuid4().hex[:5]}"
    rr = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                             "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    h = {"Authorization": f"Bearer {rr.json()['access_token']}"}
    res = client.post("/pipeline/run", headers=h, json={
        "source_id": src, "ingest_key": f"k-{uuid.uuid4().hex[:6]}", "kind": "legislation",
        "jurisdiction": "CY", "raw_payload": PAYLOAD, "canonical_id": "PL-API", "title": "T"})
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "done" and body.get("source_snapshot_id")
    assert all(v == "done" for v in body["stages"].values())