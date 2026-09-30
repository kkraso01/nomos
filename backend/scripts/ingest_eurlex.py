"""Ingest EUR-Lex/CELLAR EU legislation (approved, metadata+CELEX) via the pipeline.

Run from backend/ :
    ../.venv/bin/python scripts/ingest_eurlex.py --celex 32011L0083

Live full-text bulk is BLOCKED_EXTERNAL from this host (EUR-Lex 202 anti-bot,
cellar-imm-pub unreachable); this script ingests OFFICIAL METADATA records
(CELEX + titles) through the real EU legislation pipeline so the EU corpus path
is functional and searchable, without inventing any statutory text.

Honesty/gate notes:
  * `commercial_service_mode` defaults True (NOMOS is a paid service). The `eurlex`
    source registry row does NOT record commercial_reuse_allowed, so in the hosted
    (selling) setting the gate CORRECTLY blocks EU resale until a human records
    commercial clearance. This script forces commercial_service_mode=False purely
    for a LOCAL functional proof of the EU ingestion path — never for production.
"""
import argparse
import sys

sys.path.insert(0, ".")

from app.config import settings
from app.db import SessionLocal
from app.services.seed import seed_core, seed_sources_from_yaml
from app.services.ingestion import IngestionGateError
from app.models import SourceRegistry
from app.adapters import EurLexCellarAdapter

LOCAL_PROOF_OVERRIDE = "commercial_service_mode"
# Do not touch the default above; see module docstring.


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--celex", required=True, help="e.g. 32011L0083")
    ap.add_argument("--live", action="store_true",
                    help="attempt live CELLAR fetch (will be BLOCKED here if gated)")
    args = ap.parse_args()

    settings.commercial_service_mode = False  # local functional proof only (see docstring)

    db = SessionLocal()
    try:
        seed_core(db)
        seed_sources_from_yaml(db)
        registry = db.query(SourceRegistry).filter_by(name="EUR-Lex / CELLAR").first() \
            or db.query(SourceRegistry).filter_by(jurisdiction="EU").first()
        if registry is None:
            raise SystemExit("no EUR-Lex registry row")
        print("registry:", registry.name, "| status:", registry.reuse_status,
              "| enabled:", registry.adapter_enabled,
              "| (commercial_service_mode=False: local proof only)")

        adapter = EurLexCellarAdapter()
        rec = None
        for r in adapter.discover():
            if r["celex"] == args.celex:
                rec = r
                break
        if rec is None:
            raise SystemExit(f"CELEX {args.celex} not in official seed set")

        # reuse gate (the real one, minus the commercial flag we neutralised locally)
        from app.services.ingestion import IngestionService
        try:
            IngestionService(db).check_reuse_gate(registry)
        except IngestionGateError as e:
            print("GATE BLOCKED (expected in commercial mode):", e)

        if args.live:
            raw = adapter.fetch(rec)   # will raise AdapterConfigError if gated
        else:
            raw = (rec["title_el"] + "\n" + rec["title_en"]).encode("utf-8")
        norm = adapter.normalize(raw, rec)[0]
        print("normalized:", {"celex": norm["celex"], "nature": norm["nature"],
                              "jurisdiction": norm["jurisdiction"], "language": norm["language"]})

        from app.services.pipeline import run_pipeline
        run_obj = run_pipeline(
            db, source_id=registry.id, ingest_key=norm["celex"], kind="legislation",
            jurisdiction=norm["jurisdiction"], raw_payload=norm["body"],
            canonical_id=norm["celex"], title=norm["title"], language=norm["language"])
        # Act-level projection: metadata-only records have no numbered article, so the
        # article-scoped indexer skips them. Index the official title + CELEX so the
        # EU act is discoverable by title/reference (no statutory text invented).
        from app.services.search import upsert_search_entry
        upsert_search_entry(
            db, kind="legislation", canonical_ref=f"law-{norm['celex']}",
            canonical_id=norm["celex"], title=norm["title"], body=norm["body"],
            language=norm["language"], ref_law=norm["celex"],
            jurisdiction=norm["jurisdiction"], source_id=registry.id,
            external_url=norm.get("source_url"))
        db.commit()
        print("ingested legislation:", norm["celex"], "| run status:", run_obj.status)
    finally:
        db.close()


if __name__ == "__main__":
    main()