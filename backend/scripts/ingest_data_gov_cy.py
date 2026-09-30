"""Ingest real data.gov.cy datasets through the immutable pipeline.

Run from backend/ :
    ../.venv/bin/python -m app.adapters.notebooks... # not used
    PYTHONPATH=. ./../.venv/bin/python scripts/ingest_data_gov_cy.py --dataset consumer_decisions

Persists: SourceSnapshot (immutable raw), SourceDocument (canonical record),
LegalChunk (structural), SearchEntry (lexical projection). The licence gate
(IngestionService.check_reuse_gate) refuses anything not approved.
"""
import argparse
import csv
import io
import json
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

sys.path.insert(0, ".")
from app.db import SessionLocal
from app.services.seed import seed_core, seed_sources_from_yaml
from app.services.ingestion import IngestionService, IngestionGateError
from app.services.search import upsert_search_entry
from app.models import SourceRegistry
from app.models.core import LegalChunk
from app.adapters import DataGovCyAdapter

NS = uuid.NAMESPACE_URL


def _parse_date(raw: str):
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _upsert_chunk(db: Session, *, registry, rec, doc, snapshot_id) -> None:
    cid = uuid.uuid5(NS, f"nomos-srcdoc-{registry.id}:{rec['canonical_key']}")
    if db.get(LegalChunk, cid) is not None:
        return
    locator = {
        "authority_type": rec.get("authority_type"),
        "decision_no": rec.get("decision_no"),
        "decision_date": rec.get("decision_date_raw"),
        "legislation": rec.get("legislation"),
        "company": rec.get("company"),
        "summary": rec.get("summary"),
        "licence": rec.get("licence"),
        "licence_url": rec.get("licence_url"),
        "external_url": rec.get("external_url"),
        "dataset_key": rec.get("dataset_key"),
    }
    db.add(LegalChunk(
        id=cid, jurisdiction=registry.jurisdiction, document_type="source_document",
        document_id=doc.id, document_key=rec["canonical_key"], version_id=snapshot_id,
        chunk_type="section", text=rec["body"],
        hierarchy_context=f"{rec['title']}\nJurisdiction: {registry.jurisdiction}\n"
                          f"Type: {rec.get('authority_type', 'SOURCE_DOCUMENT')}",
        normalized_text=rec["body"], language=rec.get("language"),
        source_locator=locator, content_hash=rec["canonical_key"][:64]))
    db.flush()


def _ingest_decision(db: Session, registry, rec) -> dict:
    svc = IngestionService(db)
    svc.check_reuse_gate(registry)
    raw = json.dumps(rec, ensure_ascii=False)
    published = _parse_date(rec.get("decision_date_raw") or "")
    doc = svc.ingest_raw(
        registry, source_record_id=rec["canonical_key"], raw_payload=raw,
        canonical_key=rec["canonical_key"], title=rec["title"],
        language=rec.get("language"), mime_type="application/json",
        published_at=published)
    _upsert_chunk(db, registry=registry, rec=rec, doc=doc, snapshot_id=doc.raw_snapshot_id)
    upsert_search_entry(
        db, kind="source_document", canonical_ref=f"data-gov-cy-{rec['canonical_key']}",
        canonical_id=rec["canonical_key"], title=rec["title"], body=rec["body"],
        language=rec.get("language"), jurisdiction=registry.jurisdiction,
        source_id=registry.id, external_url=rec.get("external_url"))
    return {"canonical_key": rec["canonical_key"], "snapshot_id": doc.raw_snapshot_id,
            "title": rec["title"], "published_at": published}


def ingest_dataset(db: Session, adapter: DataGovCyAdapter, registry: SourceRegistry,
                   dataset_key: str) -> dict:
    meta = adapter.DATASETS[dataset_key]
    summary = {"dataset": dataset_key, "status": "SKIPPED", "records": 0, "reason": None}
    if meta.get("linked_on_external"):
        summary.update(status="BLOCKED_EXTERNAL", reason=(
            "substantive content lives on an external unverified host (no reusable "
            "file hosted by data.gov.cy); metadata/link-out only"))
        return summary
    # Licence re-verification at acquisition time (guardrail).
    snapshot = adapter.licence_snapshot({**meta, "dataset_key": dataset_key})
    if not snapshot["commercial_reuse_allowed"]:
        summary.update(status="BLOCKED", reason="commercial_reuse_allowed not confirmed")
        return summary
    if not meta.get("download_url"):
        summary.update(status="NOT_READY", reason="download_url not configured")
        return summary
    try:
        IngestionService(db).check_reuse_gate(registry)
    except IngestionGateError as e:
        summary.update(status="BLOCKED", reason=str(e))
        return summary
    raw = adapter.fetch(meta)
    recs = adapter.normalize(raw, {**meta, "dataset_key": dataset_key})
    n = 0
    for rec in recs:
        _ingest_decision(db, registry, rec)
        n += 1
    summary.update(status="INGESTED", records=n, raw_bytes=len(raw))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    args = ap.parse_args()
    db = SessionLocal()
    try:
        print("seed:", seed_core(db))
        print("sources:", seed_sources_from_yaml(db))
        adapter = DataGovCyAdapter()
        registry = db.query(SourceRegistry).filter_by(name="Cyprus National Open Data Portal").first()
        if registry is None:
            registry = db.query(SourceRegistry).first()
        if registry is None:
            raise SystemExit("no source registry row")
        print("registry:", registry.name, "| status:", registry.reuse_status,
              "| commercial:", registry.commercial_reuse_allowed, "| enabled:", registry.adapter_enabled)
        out = ingest_dataset(db, adapter, registry, args.dataset)
        db.commit()
        print(json.dumps(out, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()